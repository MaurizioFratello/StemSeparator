"""
Cross-Platform Foundation

PURPOSE: Single source of truth for everything that differs between macOS,
         Windows and Linux: OS identity, writable data locations, bundled
         helper-binary (FFmpeg/RubberBand) discovery, subprocess creation
         flags, multiprocessing start method and the single-instance lock.
CONTEXT: The app shipped as a macOS-only PyInstaller bundle. Every platform
         decision used to be an inline `sys.platform == "darwin"` check, which
         made the Windows/Linux paths impossible to reason about or test.
         All new platform-dependent code MUST go through this module instead of
         re-deriving the OS.

Design notes:
- OS identity is resolved lazily through `_platform_string()` so tests can
  monkeypatch `sys.platform` and still reach the branches.
- Nothing here imports third-party packages: `config.py` imports it at
  module scope, and `config.py` must stay importable in a bare interpreter.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import IO, Dict, List, Optional

APP_DIR_NAME = "StemSeparator"


# ---------------------------------------------------------------------------
# OS identity
# ---------------------------------------------------------------------------


def _platform_string() -> str:
    """Current `sys.platform` value (indirection keeps branches testable)."""
    return sys.platform


def is_macos() -> bool:
    return _platform_string() == "darwin"


def is_windows() -> bool:
    return _platform_string() == "win32"


def is_linux() -> bool:
    """Linux, and the BSD fallthrough — a `freebsd*` platform string counts."""
    plat = _platform_string()
    return plat.startswith("linux") or plat.startswith("freebsd")


def os_name() -> str:
    """Short human-readable OS label for logs, UI and the parity matrix."""
    if is_macos():
        return "macOS"
    if is_windows():
        return "Windows"
    if is_linux():
        return "Linux"
    return _platform_string() or "unknown"


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Optional[Path]:
    """Root of the PyInstaller bundle (`sys._MEIPASS`) or None in dev runs."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else None


# ---------------------------------------------------------------------------
# Writable data locations
# ---------------------------------------------------------------------------


def _env_path(var: str) -> Optional[Path]:
    value = os.environ.get(var)
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else None


def user_data_dir() -> Path:
    """
    Persistent, user-writable directory for settings, logs and caches.

    WHY: Each OS has a conventional location, and writing next to the app
         bundle breaks under Windows `Program Files` ACLs and inside a
         read-only PyInstaller `_MEIPASS`.
         macOS  -> ~/Library/Application Support/StemSeparator
         Windows-> %LOCALAPPDATA%\\StemSeparator (falls back to %APPDATA%)
         Linux  -> $XDG_DATA_HOME/StemSeparator (falls back to ~/.local/share)
    """
    if is_macos():
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME

    if is_windows():
        for var in ("LOCALAPPDATA", "APPDATA"):
            base = _env_path(var)
            if base:
                return base / APP_DIR_NAME
        return Path.home() / APP_DIR_NAME

    xdg = _env_path("XDG_DATA_HOME")
    if xdg:
        return xdg / APP_DIR_NAME
    return Path.home() / ".local" / "share" / APP_DIR_NAME


def user_cache_dir() -> Path:
    """
    Re-downloadable data (model weights, FFmpeg probes) lives here.

    WHY: Separation models are hundreds of MB and can always be re-fetched;
         they must not bloat the roaming profile on Windows or the backed-up
         data directory on Linux/macOS.
    """
    if is_macos():
        return Path.home() / "Library" / "Caches" / APP_DIR_NAME

    if is_windows():
        for var in ("LOCALAPPDATA", "APPDATA"):
            base = _env_path(var)
            if base:
                return base / APP_DIR_NAME / "Cache"
        return Path.home() / APP_DIR_NAME / "Cache"

    xdg = _env_path("XDG_CACHE_HOME")
    if xdg:
        return xdg / APP_DIR_NAME
    return Path.home() / ".cache" / APP_DIR_NAME


def music_dir() -> Path:
    """
    Default location for user-facing audio output.

    WHY: macOS and Windows ship a known Music folder; on Linux the XDG user
         dirs may be missing (headless/minimal installs), so fall back to
         ~/Music and finally ~/Documents rather than failing.
    """
    if is_windows():
        profile = _env_path("USERPROFILE") or Path.home()
        music = profile / "Music"
        if music.exists():
            return music
        return _documents_fallback(profile)

    music = Path.home() / "Music"
    if music.exists():
        return music
    xdg_music = _env_path("XDG_MUSIC_DIR")
    if xdg_music and xdg_music.exists():
        return xdg_music
    documents = Path.home() / "Documents"
    return documents if documents.exists() else music


def _documents_fallback(profile: Path) -> Path:
    documents = profile / "Documents"
    return documents if documents.exists() else profile


# ---------------------------------------------------------------------------
# Bundled helper executables (FFmpeg / RubberBand)
# ---------------------------------------------------------------------------

# Naming convention used by the two popular FFmpeg build distributors; the
# Windows build is unpacked next to the app as `ffmpeg-master-latest-win64-gpl`.
FFMPEG_WINDOWS_DIRNAME = "ffmpeg-master-latest-win64-gpl"


def executable_name(name: str) -> str:
    """`ffmpeg` -> `ffmpeg.exe` on Windows, unchanged elsewhere."""
    return f"{name}.exe" if is_windows() else name


def bundled_binary_dirs() -> List[Path]:
    """
    Directories inside the bundle that may hold FFmpeg/RubberBand binaries.

    WHY: The macOS bundle historically used `.app/Contents/Frameworks`,
         PyInstaller's own data dir is `sys._MEIPASS` (`_internal` for onedir),
         and the Windows FFmpeg release unpacks into a versioned subfolder.
         Checking all of them keeps one build recipe working everywhere.
    """
    candidates: List[Path] = []

    if is_frozen():
        root = bundle_dir() or Path.cwd()
        candidates += [
            root / "bin",
            root / "resources" / "bin",
            root / "_internal" / "bin",
            root / "_internal" / "resources" / "bin",
        ]
        if is_windows():
            candidates += [
                root / FFMPEG_WINDOWS_DIRNAME / "bin",
                root / "ffmpeg" / "bin",
            ]
        elif is_macos():
            mac_root = _macos_bundle_root()
            if mac_root:
                candidates += [
                    mac_root / "Contents" / "Frameworks",
                    mac_root / "Contents" / "Resources" / "bin",
                ]

    # Development checkout: `packaging/vendor/bin` after running the
    # binary-download helper.
    from_source = Path(__file__).resolve().parent.parent / "packaging" / "vendor" / "bin"
    candidates.append(from_source)

    return [path for path in candidates if path.is_dir()]


def _macos_bundle_root() -> Optional[Path]:
    """`.app` root when frozen by PyInstaller on macOS."""
    if not (is_frozen() and is_macos()):
        return None
    try:
        path = Path(sys.executable).resolve()
    except OSError:
        return None
    for parent in [path] + list(path.parents):
        if parent.suffix == ".app":
            return parent
    return None


def system_binary_dirs() -> List[Path]:
    """
    Well-known install locations for FFmpeg, used as PATH fallback.

    WHY: `brew install ffmpeg` (Intel + Apple Silicon), the Windows package
         layout and the Linux distro paths are all predictable; probing them
         lets users who installed FFmpeg themselves work without touching PATH.
    """
    if is_macos():
        return [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    if is_windows():
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        return [
            Path(program_files) / "ffmpeg" / "bin",
            Path(program_files) / "FFmpeg" / "bin",
        ]
    return [Path("/usr/bin"), Path("/usr/local/bin")]


def find_binary(name: str) -> Optional[Path]:
    """
    Resolve an external tool (`ffmpeg`, `rubberband`) to an absolute path.

    Order: bundled dirs -> PATH -> well-known install dirs.
    """
    exe = executable_name(name)

    for directory in bundled_binary_dirs():
        candidate = directory / exe
        if candidate.is_file():
            return candidate

    on_path = shutil.which(name) or shutil.which(exe)
    if on_path:
        return Path(on_path)

    for directory in system_binary_dirs():
        candidate = directory / exe
        if candidate.is_file():
            return candidate

    return None


def has_binary(name: str) -> bool:
    return find_binary(name) is not None


def ensure_binaries_on_path(extra_dirs: Optional[List[Path]] = None) -> List[Path]:
    """
    Prepend bundle + known tool directories to `PATH` for this process.

    WHY: `audio-separator`, `pydub` and `pyrubberband` shell out via
         `subprocess` and therefore only look at `PATH`. Child processes
         inherit the modified environment, which is how the separation
         subprocess finds the bundled FFmpeg.
    """
    ordered: List[Path] = []
    for directory in (extra_dirs or []) + bundled_binary_dirs() + system_binary_dirs():
        if directory.is_dir() and directory not in ordered:
            ordered.append(directory)

    if not ordered:
        return []

    existing = os.environ.get("PATH", "")
    parts = [p for p in existing.split(os.pathsep) if p]
    prepend = [str(d) for d in ordered if str(d) not in parts]
    if prepend:
        os.environ["PATH"] = os.pathsep.join(prepend + parts)
    return ordered


def configure_native_library_dirs(extra_dirs: Optional[List[Path]] = None) -> List[Path]:
    """
    Register DLL search directories on Windows (no-op on other platforms).

    WHY: PyInstaller onedir builds ship `torch`, cuDNN and cuBLAS DLLs in
         `_internal`; Python 3.8+ no longer searches PATH for DLLs, so a
         bundled CUDA-enabled torch raises `ImportError: DLL load failed`
         unless each directory is added with `os.add_dll_directory`.
    """
    if not is_windows():
        return []

    added: List[Path] = []
    for directory in (extra_dirs or []) + bundled_binary_dirs():
        if not directory.is_dir():
            continue
        try:
            os.add_dll_directory(str(directory))
            added.append(directory)
        except (OSError, AttributeError):
            continue
    return added


def torch_library_dirs() -> List[Path]:
    """
    Directories inside the bundle that hold torch/CUDA DLLs on Windows.

    WHY: PyInstaller collects `torch` into `_internal/torch/lib` and the CUDA
         runtime DLLs next to it; both must be on the DLL path before torch is
         imported (see PKG-03/PKG-04).
    """
    if not (is_windows() and is_frozen()):
        return []

    root = bundle_dir() or Path.cwd()
    candidates = [
        root / "_internal" / "torch" / "lib",
        root / "torch" / "lib",
        root / "_internal" / "torch" / "bin",
        root / "_internal" / "nvidia",
    ]
    return [path for path in candidates if path.is_dir()]


# ---------------------------------------------------------------------------
# Subprocess behaviour
# ---------------------------------------------------------------------------

CREATE_NO_WINDOW = 0x08000000  # subprocess.CREATE_NO_WINDOW


def popen_kwargs() -> Dict[str, object]:
    """
    `subprocess.Popen`/`run` keyword arguments for a hidden helper process.

    WHY: On Windows a bare `Popen` flashes a console window for every
         FFmpeg/BeatNet call; on POSIX the equivalent need is a detached
         session so Ctrl-C in a terminal does not kill the GUI's workers.
    """
    if is_windows():
        return {"creationflags": CREATE_NO_WINDOW}
    return {"start_new_session": True}


def popen_kwargs_for_console() -> Dict[str, object]:
    """Flags for helpers that legitimately need their own console (BeatNet)."""
    if is_windows():
        return {"creationflags": 0x00000010}  # DETACHED_PROCESS
    return {"start_new_session": True}


def multiprocessing_start_method() -> str:
    """
    Force `spawn` everywhere.

    WHY: CUDA must not be used in a forked child (the parent's CUDA context is
         invalid after fork), and `fork` is unavailable on Windows to begin
         with. `spawn` matches the documented PyTorch requirement and keeps one
         behaviour on all three platforms.
    """
    return "spawn"


def configure_multiprocessing() -> Optional[str]:
    """
    Set the multiprocessing start method to `spawn` when not already chosen.

    Returns the effective method, or None when the platform/context forbids it.
    """
    import multiprocessing as mp

    try:
        try:
            current = mp.get_start_method(allow_none=True)
        except RuntimeError:  # already set explicitly elsewhere
            return mp.get_start_method()
        if current is None:
            mp.set_start_method(multiprocessing_start_method(), force=True)
        return mp.get_start_method()
    except (ValueError, RuntimeError) as exc:  # pragma: no cover - defensive
        sys.stderr.write(f"Could not set multiprocessing start method: {exc}\n")
        return None


def numba_cuda_safe_env() -> Dict[str, str]:
    """
    Environment overrides that keep numba from initialising CUDA too early.

    WHY: audio-separator pulls in numba; when numba initialises the CUDA
         driver before torch does, the parent CUDA context leaks into the
         spawned worker and separation dies with a `CUDA context` error.
         numba's own docs prescribe `NUMBA_DISABLE_CU_INIT`.
    """
    env = {}
    if not is_macos():
        env.setdefault("NUMBA_DISABLE_CU_INIT", "1")
    return env


# ---------------------------------------------------------------------------
# Single-instance lock
# ---------------------------------------------------------------------------


class InstanceLock:
    """
    Advisory single-instance lock backed by an OS file lock.

    WHY: The original implementation imported `fcntl` at module scope, which is
         unavailable on Windows and crashed startup before the GUI appeared.
         `fcntl.flock` on POSIX and `msvcrt.locking` on Windows both release
         automatically when the process dies, so a crash never strands the lock.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._handle: Optional[IO[bytes]] = None
        self._backend: Optional[str] = None

    @property
    def acquired(self) -> bool:
        return self._handle is not None

    def acquire(self) -> bool:
        """Try to take the lock; False when another instance holds it."""
        if self._handle is not None:
            return True

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False

        # `a+b` keeps an existing file (and its content) but still allows
        # truncate-after-lock, and opening for writing is what both lock
        # APIs need a file descriptor for.
        handle = open(self.path, "a+b")

        if self._acquire_posix(handle) or self._acquire_windows(handle):
            self._handle = handle
            self._write_pid()
            return True

        handle.close()
        return False

    def _acquire_posix(self, handle: IO[bytes]) -> bool:
        if is_windows():
            return False
        try:
            import fcntl
        except ImportError:  # pragma: no cover - exotic platform
            return False
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        self._backend = "fcntl"
        return True

    def _acquire_windows(self, handle: IO[bytes]) -> bool:
        if not is_windows():
            return False
        try:
            import msvcrt
        except ImportError:  # pragma: no cover - not on POSIX
            return False
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        self._backend = "msvcrt"
        return True

    def _write_pid(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            self._handle.write(f"{os.getpid()}\n".encode())
            self._handle.truncate()
            self._handle.flush()
        except OSError:  # pragma: no cover - lock already held, PID is cosmetic
            pass

    def release(self) -> None:
        """Unlock, close and remove the lock file."""
        handle, self._handle, self._backend = self._handle, None, None
        if handle is None:
            return

        try:
            if self._backend == "msvcrt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            elif self._backend == "fcntl":
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            try:
                handle.close()
            except OSError:
                pass
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Runtime report (diagnostics, logs, about box)
# ---------------------------------------------------------------------------


def runtime_report() -> Dict[str, object]:
    """
    Snapshot of the platform contract, for logs and bug reports.

    WHY: Windows/Linux bug reports are unactionable without knowing whether
         FFmpeg/RubberBand were found and where data is being written.
    """
    from utils.logger import get_logger

    logger = get_logger()
    ffmpeg = find_binary("ffmpeg")
    ffprobe = find_binary("ffprobe")
    rubberband = find_binary("rubberband")

    report: Dict[str, object] = {
        "os": os_name(),
        "platform": _platform_string(),
        "frozen": is_frozen(),
        "data_dir": str(user_data_dir()),
        "cache_dir": str(user_cache_dir()),
        "ffmpeg": str(ffmpeg) if ffmpeg else None,
        "ffprobe": str(ffprobe) if ffprobe else None,
        "rubberband": str(rubberband) if rubberband else None,
        "multiprocessing": multiprocessing_start_method(),
    }
    logger.debug(f"Platform runtime report: {report}")
    return report
