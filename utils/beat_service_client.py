"""
BeatNet Beat-Service Client

PURPOSE: Python wrapper to invoke the BeatNet beat-service binary
CONTEXT: Runs beat-service as subprocess, handles JSON I/O, timeouts, errors

The beat-service binary is a separate executable built with PyInstaller
from a Python 3.8/3.9 environment (required for BeatNet/numba compatibility).

WHY the client is platform-driven: the binary historically only resolved on
macOS - a bare `beatnet-service` name does not exist on Windows, where the
executable carries an `.exe` suffix and lives next to the app bundle. All OS
decisions (name mangling, bundle layout, process-group flags) therefore go
through `utils.platform_utils`, mirroring how the separation worker is spawned.

The client never installs or mutates packages: the service environment
(BeatNet, madmom, numba, torch) is owned by packaging, and a runtime bootstrap
that reinstalled a dependency could silently replace a CUDA-enabled torch
build with a CPU wheel. A broken service environment must surface as a
`BeatServiceError` so the caller falls back visibly, not as a surprise install.
"""

import sys
import os
import json
import shutil
import signal
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Literal, Callable

from utils.logger import get_logger
from utils import platform_utils

logger = get_logger()

# Type definitions
BeatBackend = Literal["cpu", "mps", "cuda", "auto"]

#: Base name of the PyInstaller-built helper (`.exe` is appended on Windows).
BEAT_SERVICE_BINARY = "beatnet-service"

#: Accepted spellings. The PyInstaller spec and `build.sh` emit
#: `beatnet-service`; `beatnet_service` (underscore) is kept because the
#: Windows packaging notes and user copies of the helper use it.
BEAT_SERVICE_BINARY_NAMES = ("beatnet-service", "beatnet_service")

#: Explicit path to the helper, for QA runs and custom installs.
BEAT_SERVICE_ENV_VAR = "STEMSEPARATOR_BEAT_SERVICE"

#: Interpreter used by the source-mode fallback (dev checkouts, CI).
BEAT_SERVICE_PYTHON_ENV_VAR = "STEMSEPARATOR_BEAT_SERVICE_PYTHON"

#: `subprocess.CREATE_NEW_PROCESS_GROUP`; spelled out because subprocess does
#: not export the constant on every supported Python version.
CREATE_NEW_PROCESS_GROUP = 0x00000200

#: Grace period granted to each termination stage (SIGINT/Ctrl-Break -> SIGTERM -> kill).
TERMINATION_GRACE_SECONDS = 2.0

_VALID_DEVICES = ("cpu", "mps", "cuda", "auto")

#: One-shot latch so the source-mode fallback is announced once per process.
_LAUNCH_MODE_ANNOUNCED = [False]


# ============================================================================
# Data Classes (PRD Section 4.3.1)
# ============================================================================


@dataclass
class Beat:
    """A single beat in the track."""

    time: float  # Seconds from track start
    index: int  # Running beat index (0-based)
    bar: Optional[int] = None  # Bar number (1-based), if known
    beat_in_bar: Optional[int] = None  # Position in bar (e.g., 1..4 for 4/4)


@dataclass
class Downbeat:
    """Start of a bar (downbeat)."""

    time: float  # Seconds
    bar: int  # Bar number (1-based)


@dataclass
class BeatAnalysisResult:
    """Result of BeatNet analysis."""

    tempo: float
    tempo_confidence: float
    time_signature: str
    beats: List[Beat]
    downbeats: List[Downbeat]
    analysis_duration: float
    audio_duration: Optional[float] = None
    backend: Optional[str] = None  # cpu/mps/cuda
    warnings: Optional[List[str]] = None


@dataclass
class BeatServiceLaunch:
    """How to start the beat service, plus a label for the log."""

    argv: List[str]
    cwd: Optional[Path]
    kind: str  # 'binary' | 'module'
    location: Path  # helper binary, or the service source directory


# ============================================================================
# Exceptions (PRD Section 4.3.2)
# ============================================================================


class BeatServiceError(Exception):
    """General error from beat service."""

    pass


class BeatServiceTimeout(BeatServiceError):
    """Timeout waiting for beat service."""

    pass


class BeatServiceNotFound(BeatServiceError):
    """Beat service binary not found."""

    pass


# ============================================================================
# Binary Discovery
# ============================================================================


def _project_root() -> Path:
    """Repository root, derived from this file's location."""
    return Path(__file__).resolve().parent.parent


def _binary_names() -> List[str]:
    """
    Executable names to probe for the helper.

    WHY: on Windows a name without `.exe` is only found when PATHEXT kicks in,
         which `shutil.which` does but a plain `directory / name` check does
         not. Probing both spellings makes PATH lookup and the explicit
         candidate list behave identically on all three platforms.
    """
    names: List[str] = []
    for base in BEAT_SERVICE_BINARY_NAMES:
        for candidate in (platform_utils.executable_name(base), base):
            if candidate not in names:
                names.append(candidate)
    return names


def _binary_search_dirs() -> List[Path]:
    """
    Directories that may contain the helper, in precedence order.

    WHY: the packaged layouts differ per OS - PyInstaller onefile unpacks into
         `sys._MEIPASS`, onedir keeps data in `_internal`, the macOS `.app`
         carries the helper next to the executable in `Contents/MacOS`, and a
         dev checkout has it under `packaging/beatnet_service/dist/`. One
         ordered list keeps the shipped app, the installer and `./build.sh`
         working without platform branching inside the lookup itself.
    """
    project_root = _project_root()
    service_dir = project_root / "packaging" / "beatnet_service"

    dirs: List[Path] = []

    override = os.environ.get(BEAT_SERVICE_ENV_VAR)
    if override:
        parent = Path(override).expanduser().parent
        if parent.is_dir():
            dirs.append(parent)

    if platform_utils.is_frozen():
        bundle = platform_utils.bundle_dir()
        if bundle is not None:
            dirs += [
                bundle,
                bundle / "bin",
                bundle / "resources" / "bin",
                bundle / "_internal",
                bundle / "_internal" / "bin",
            ]
        # Directory holding the app executable: `Contents/MacOS` for the macOS
        # bundle, the install folder for the Windows exe.
        try:
            dirs.append(Path(sys.executable).resolve().parent)
        except OSError:  # pragma: no cover - unreadable executable path
            pass

    # Development checkout.
    dirs += [
        service_dir / "dist",
        service_dir,
        project_root / "resources" / "beatnet",
    ]

    dirs += platform_utils.bundled_binary_dirs() + platform_utils.system_binary_dirs()

    unique: List[Path] = []
    for directory in dirs:
        if directory.is_dir() and directory not in unique:
            unique.append(directory)
    return unique


def _is_executable_file(path: Path) -> bool:
    """True when `path` is a file the OS is allowed to launch."""
    if not path.is_file():
        return False
    if platform_utils.is_windows():
        # Windows has no executable bit and `os.access(X_OK)` only reflects
        # read-only status there, so the extension is the real signal.
        return True
    return os.access(path, os.X_OK)


def _find_beat_service_binary() -> Optional[Path]:
    """
    Locate the beatnet-service binary.

    Search order:
    1. `STEMSEPARATOR_BEAT_SERVICE` override
    2. PyInstaller bundle (`sys._MEIPASS`, `_internal`, macOS `Contents/MacOS`)
    3. Development checkout (`packaging/beatnet_service/dist`, the service
       directory itself, `resources/beatnet`)
    4. `PATH` through `shutil.which`
    5. Well-known system install directories

    Platform note: every candidate is also tried with the `.exe` suffix, which
    is how the helper is found on Windows (`beatnet-service.exe`).

    Returns:
        Path to binary or None if not found
    """
    names = _binary_names()

    override = os.environ.get(BEAT_SERVICE_ENV_VAR)
    if override:
        candidate = Path(override).expanduser()
        if _is_executable_file(candidate):
            logger.debug(f"Using beatnet-service override: {candidate}")
            return candidate
        logger.warning(
            f"{BEAT_SERVICE_ENV_VAR} points to a file that cannot be executed: {candidate}"
        )

    searched: List[str] = []
    for directory in _binary_search_dirs():
        for name in names:
            candidate = directory / name
            searched.append(str(candidate))
            if _is_executable_file(candidate):
                logger.debug(f"Found beatnet-service at: {candidate}")
                return candidate
            if candidate.is_file():
                logger.warning(f"Found beatnet-service but not executable: {candidate}")

    for name in names:
        on_path = shutil.which(name)
        if on_path:
            candidate = Path(on_path)
            if _is_executable_file(candidate):
                logger.debug(f"Found beatnet-service on PATH: {candidate}")
                return candidate

    # NOT a warning: `is_beat_service_available()` is called on every analysis
    # and a checkout without a built helper legitimately falls back to
    # source mode. `_service_launch_spec()` reports the outcome once instead.
    logger.debug(
        "beatnet-service binary not found; searched: "
        + ", ".join(searched[:8])
        + (" ..." if len(searched) > 8 else "")
    )
    return None


def _find_beat_service_module() -> Optional[BeatServiceLaunch]:
    """
    Fall back to running the service from source with an interpreter.

    WHY: the PyInstaller helper is a build artifact (git-ignored
         `packaging/beatnet_service/dist/`), so a checkout that never ran
         `build.sh` has no binary on any platform - precisely the situation on
         fresh Linux/Windows installs. Running `python -m src` inside the
         service folder reproduces the documented development workflow
         (`packaging/beatnet_service/README.md`) over the same JSON IPC.
         Deliberately disabled when frozen: inside a bundle `sys.executable`
         is the app itself, which would start a second GUI.
    """
    if platform_utils.is_frozen():
        return None

    service_dir = _project_root() / "packaging" / "beatnet_service"
    if not (service_dir / "src" / "__main__.py").is_file():
        return None

    python = os.environ.get(BEAT_SERVICE_PYTHON_ENV_VAR) or sys.executable
    if not python or not Path(python).is_file():
        logger.warning(
            f"Beat service interpreter not usable: {python!r}; "
            "build the binary with packaging/beatnet_service/build.sh"
        )
        return None

    logger.debug(f"Using beatnet-service from source: {python} -m src in {service_dir}")
    return BeatServiceLaunch(
        argv=[python, "-m", "src"],
        cwd=service_dir,
        kind="module",
        location=service_dir,
    )


def _service_launch_spec() -> Optional[BeatServiceLaunch]:
    """
    Decide how the beat service should be started.

    Returns:
        `BeatServiceLaunch`, or None when neither a binary nor the source tree
        is usable.
    """
    binary = _find_beat_service_binary()
    if binary is not None:
        return BeatServiceLaunch(
            argv=[str(binary)], cwd=binary.parent, kind="binary", location=binary
        )

    module_launch = _find_beat_service_module()
    if module_launch is not None and not _LAUNCH_MODE_ANNOUNCED[0]:
        # WHY once per process: without the packaged helper this fallback is
        # the normal state of a source checkout, not an error - but it has to
        # be visible in the log, because BeatNet then runs in the app's own
        # Python environment instead of the isolated one.
        _LAUNCH_MODE_ANNOUNCED[0] = True
        logger.info(
            "beatnet-service binary not found; running the beat service from "
            f"source ({module_launch.location}). Build the helper with "
            "packaging/beatnet_service/build.sh for a standalone install."
        )
    return module_launch


def is_beat_service_available() -> bool:
    """
    Check if the beat-service can be launched (packaged binary or source mode).

    Returns:
        True if the service can be started
    """
    return _service_launch_spec() is not None


# ============================================================================
# Device policy
# ============================================================================


_device_manager_singleton = None


def _device_manager():
    """
    Lazily reach the app-wide `DeviceManager`.

    WHY lazy: importing `core.device_manager` pulls in `config` and eventually
         torch; a module-level import would make every import of this client
         (including from `utils/beatnet_warmup.py` and from unit tests) pay for
         a CUDA context it may never use.
    """
    global _device_manager_singleton
    if _device_manager_singleton is None:
        from core.device_manager import get_device_manager

        _device_manager_singleton = get_device_manager()
    return _device_manager_singleton


def _select_device(requested: BeatBackend) -> str:
    """
    Resolve a device request into the concrete `--device` value for the service.

    Args:
        requested: 'auto', 'cuda', 'mps' or 'cpu'

    Returns:
        'cuda', 'mps' or 'cpu'

    Raises:
        BeatServiceError: when the request cannot be honoured - an unavailable
            pin is refused, never quietly turned into CPU.

    WHY the client resolves the device instead of forwarding 'auto': the
         service is an isolated binary with its own torch build and has no
         access to the app settings (`compute_device`, `use_gpu`). Resolving
         here keeps one policy - `core.device_manager` - in charge of
         separation and beat analysis alike; the service only has to verify the
         concrete device it was handed.
    """
    name = (requested or "auto").strip().lower()
    if name not in _VALID_DEVICES:
        raise BeatServiceError(
            f"Unknown beat-analysis device '{requested}'; expected auto, cuda, mps or cpu."
        )

    if name == "mps" and not platform_utils.is_macos():
        # WHY: MPS does not exist off macOS; asking for it used to end in a
        # silent CPU run that looked like "BeatNet is just slow".
        raise BeatServiceError(
            "Device 'mps' requires macOS "
            f"(running on {platform_utils.os_name()}); use 'cuda', 'cpu' or 'auto'."
        )

    manager = _device_manager()

    if name == "auto":
        device = (manager.get_device() or "cpu").strip().lower()
        if device not in ("cpu", "mps", "cuda"):
            device = "cpu"
        if device == "mps" and not platform_utils.is_macos():
            # Defensive: a probe cannot yield MPS here, refuse rather than ask.
            logger.warning(
                "DeviceManager reported MPS on a non-macOS platform; "
                "declining to request it."
            )
            cuda_info = manager.get_device_info("cuda")
            device = "cuda" if cuda_info is not None and cuda_info.available else "cpu"
        logger.info(
            f"BeatNet device: {device} "
            f"({manager.selection_reason or 'auto-selected by DeviceManager'})"
        )
        if device == "cpu":
            cuda_info = manager.get_device_info("cuda")
            if cuda_info is not None and not cuda_info.available:
                # WHY: an automatic CPU choice is exactly where users report
                # "the app ignores my GPU"; the description DeviceManager
                # computed (CPU-only wheel, rejected driver, no PyTorch) names
                # the cause instead of leaving it a silent fallback.
                logger.warning(f"BeatNet running on CPU: {cuda_info.description}")
        return device

    info = manager.get_device_info(name)
    if info is None or not getattr(info, "available", False):
        detail = getattr(info, "description", None) or manager.last_error or "unknown"
        raise BeatServiceError(f"Device '{name}' unusable for beat analysis: {detail}")

    # WHY not `manager.set_device(name)`: DeviceManager is a process-wide
    # singleton and set_device() repoints the separator and the player too.
    # The beat service runs in its own process, so validating availability is
    # enough and leaves the rest of the app on its configured device.
    logger.info(f"BeatNet device: {name} (explicitly requested)")
    return name


# ============================================================================
# Subprocess setup and teardown
# ============================================================================


def _service_popen_kwargs() -> dict:
    """
    `Popen` flags for the beat service on the current OS.

    WHY: POSIX needs the child to lead its own session (`os.setsid`, i.e.
         `start_new_session=True`) so `killpg` can reach everything it spawns
         and a terminal Ctrl-C cannot take the GUI down with it. Windows has no
         sessions; there the child needs `CREATE_NEW_PROCESS_GROUP` so
         `CTRL_BREAK_EVENT` targets only this tree, on top of the console flags
         from `platform_utils.popen_kwargs_for_console()` that stop a console
         window from flashing for every analysis.
    """
    kwargs: dict = dict(platform_utils.popen_kwargs_for_console())
    if platform_utils.is_windows():
        kwargs["creationflags"] = (
            int(kwargs.get("creationflags", 0) or 0) | CREATE_NEW_PROCESS_GROUP
        )
    return kwargs


def _service_env() -> dict:
    """
    Environment for the service process.

    WHY: `NUMBA_DISABLE_CU_INIT` stops numba (pulled in by madmom/BeatNet) from
         creating a CUDA context before torch does - the same protection the
         separation worker gets.
    """
    env = dict(os.environ)
    env.update(platform_utils.numba_cuda_safe_env())
    return env


def _wait_for_exit(process: subprocess.Popen, timeout: float) -> bool:
    """Reap `process` within `timeout`, reporting whether it exited."""
    deadline = time.monotonic() + max(timeout, 0.0)
    while True:
        if process.poll() is not None:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def _close_pipes(process: subprocess.Popen) -> None:
    """
    Close the stdio pipes so the child can exit and the FDs are released.

    WHY: waiting without draining can hang forever when the child filled the
         OS pipe buffer and is blocked in `write`.
    """
    for stream in (process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            stream.close()
        except OSError:
            pass


def _taskkill_tree(process: subprocess.Popen) -> bool:
    """
    Force-kill a Windows process tree with `taskkill /T /F`.

    Returns:
        True when taskkill could be run (even if the child had already exited).

    WHY: the PyInstaller onefile bootloader spawns a second Python process;
         killing only the parent orphans the real worker, which keeps the audio
         file, GPU memory and CPU busy. `/T` walks the whole tree.
    """
    taskkill = shutil.which("taskkill") or str(
        Path(os.environ.get("WINDIR", "C:\\Windows")) / "System32" / "taskkill.exe"
    )
    try:
        result = subprocess.run(
            [taskkill, "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=10,
            **platform_utils.popen_kwargs(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug(f"taskkill could not run: {exc}")
        return False
    if result.returncode != 0:
        logger.debug(
            "taskkill exited "
            f"{result.returncode}: {(result.stdout or result.stderr or '').strip()}"
        )
    return True


def _group_still_has_members(pgid: int) -> bool:
    """True when at least one live process is left in process group `pgid`."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except OSError:  # EPERM and friends: nothing safe to conclude
        return False
    return True


def _terminate_process(process: subprocess.Popen) -> None:
    """
    Terminate the beat service (and everything it spawned), portably.

    Strategy:
    - POSIX: the child leads its own session, so signal the whole **group** -
      SIGINT (graceful shutdown) -> SIGTERM -> SIGKILL - escalating until the
      group is empty, not merely until the direct child exits.
    - Windows: there is no SIGINT. Send CTRL_BREAK_EVENT to the process group
      created for the child, then `taskkill /T /F`, then `kill()`.

    WHY the group has to be drained instead of just the child: the service is
    often an interpreter or a PyInstaller bootloader that spawns the real
    worker as a second process, and POSIX gives asynchronous (`&`) children of
    a non-interactive shell an ignored SIGINT. Stopping as soon as the leader
    exits therefore leaves the actual BeatNet process running - burning CPU
    and holding the GPU - while the app believes the analysis was cancelled.

    WHY escalation instead of an immediate kill: letting BeatNet unwind keeps
    the CUDA driver from holding on to a torn-down context, while the
    escalation bounds the damage when the child ignores the polite signal.
    """
    if process is None:
        return
    if process.poll() is not None:
        _close_pipes(process)
        return

    grace = TERMINATION_GRACE_SECONDS

    try:
        if platform_utils.is_windows():
            try:
                os.kill(process.pid, signal.CTRL_BREAK_EVENT)
                if _wait_for_exit(process, grace):
                    _close_pipes(process)
                    return
            except (OSError, ValueError, AttributeError) as exc:
                logger.debug(f"CTRL_BREAK_EVENT could not be delivered: {exc}")

            if _taskkill_tree(process) and _wait_for_exit(process, grace):
                _close_pipes(process)
                return
        else:
            # Capture the group up front: once the leader is reaped, getpgid()
            # on its pid fails while its workers are still alive.
            try:
                pgid = os.getpgid(process.pid)
            except OSError:
                pgid = None

            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
                if pgid is not None:
                    try:
                        os.killpg(pgid, sig)
                    except ProcessLookupError:
                        pgid = None
                    except OSError as exc:
                        logger.debug(f"killpg({int(sig)}) failed: {exc}")
                        pgid = None
                if pgid is None:
                    # Not a session leader (launched without our flags):
                    # signal the process itself.
                    try:
                        process.send_signal(sig)
                    except (OSError, ValueError):
                        break
                if _wait_for_exit(process, grace):
                    if pgid is None or not _group_still_has_members(pgid):
                        _close_pipes(process)
                        return
                    # Leader gone, workers alive: escalate to the next signal.
            if pgid is not None:
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except OSError:
                    pass

        # Last resort on every platform.
        try:
            process.kill()
        except (OSError, ValueError):
            pass
        _wait_for_exit(process, grace)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Error terminating beat service process: {e}")
    finally:
        _close_pipes(process)


# ============================================================================
# Main API (PRD Section 4.3.2)
# ============================================================================


def _log_service_stderr(stderr: str) -> None:
    """
    Relay the service's stderr into the app log.

    WHY: the device and error lines decide whether a BPM result can be trusted,
         so they are logged at INFO; BeatNet's own progress chatter stays DEBUG.
    """
    for line in (stderr or "").strip().splitlines():
        if not line.strip():
            continue
        lowered = line.lower()
        if "device" in lowered or "error" in lowered or "traceback" in lowered:
            logger.info(line)
        else:
            logger.debug(line)


def _parse_service_json(stdout: str, *, what: str) -> dict:
    """
    Parse the JSON document the service printed on stdout.

    WHY the fallback scan: stdout is this service's IPC channel, but the
         frozen dependency stack does not always keep it clean - PyAudio, for
         example, answers a broken C extension with a bare `print()`. Losing a
         valid analysis to one line of third-party chatter would be a
         regression on every platform, so the outermost JSON object is
         extracted when a strict parse fails.

    Args:
        stdout: raw stdout of the service
        what: label used in the error message ('result' or 'error')

    Raises:
        BeatServiceError: when no JSON object can be found.
    """
    text = (stdout or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise BeatServiceError(
        f"Invalid JSON from beat service ({what}): no JSON object in "
        f"output: {text[:500]!r}"
    )


def analyze_beats(
    audio_path: Path,
    *,
    max_duration: Optional[float] = None,
    device: BeatBackend = "auto",
    timeout_seconds: float = 60.0,
    process_callback: Optional[Callable[[subprocess.Popen], None]] = None,
) -> BeatAnalysisResult:
    """
    Run beat analysis via BeatNet service subprocess.

    Args:
        audio_path: Path to audio file
        max_duration: Optional limit on analysis duration (seconds)
        device: Compute device ('cpu', 'mps', 'cuda', 'auto'); resolved through
                `core.device_manager` before the service is started
        timeout_seconds: Maximum time to wait for analysis
        process_callback: Optional callback function called with subprocess
                         after it's created. Useful for tracking/cancellation.

    Returns:
        BeatAnalysisResult with tempo, beats, downbeats

    Raises:
        FileNotFoundError: If audio file doesn't exist
        BeatServiceNotFound: If no service binary and no source tree are usable
        BeatServiceTimeout: If analysis exceeds timeout
        BeatServiceError: For other errors (unusable device, non-zero exit, bad JSON)

    Example:
        >>> result = analyze_beats(Path("song.wav"), timeout_seconds=30.0)
        >>> print(f"Tempo: {result.tempo:.1f} BPM")
        >>> print(f"Beats: {len(result.beats)}, Downbeats: {len(result.downbeats)}")
    """
    # Validate input
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Find the service (binary, or the source-mode fallback)
    launch = _service_launch_spec()
    if launch is None:
        raise BeatServiceNotFound(
            "beatnet-service binary not found. "
            "Build it with: cd packaging/beatnet_service && ./build.sh, "
            f"or point {BEAT_SERVICE_ENV_VAR} at an existing build."
        )

    # Resolve device policy before spending time on the subprocess
    resolved_device = _select_device(device)

    # Build command
    cmd = [
        *launch.argv,
        "--input",
        str(audio_path.absolute()),
        "--output",
        "-",  # stdout
        "--device",
        resolved_device,
        "--verbose",
    ]

    if max_duration is not None:
        cmd.extend(["--max-duration", str(max_duration)])

    logger.info(
        f"Starting beat analysis: {audio_path.name} "
        f"(service: {launch.kind} {launch.location}, device: {resolved_device})"
    )
    logger.debug(f"Command: {' '.join(cmd)}")

    process = None
    try:
        # Start subprocess
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            cwd=str(launch.cwd) if launch.cwd is not None else None,
            env=_service_env(),
            **_service_popen_kwargs(),
        )

        # Call callback with subprocess reference if provided
        # WHY: Allows caller to track/terminate subprocess for cancellation
        if process_callback:
            try:
                process_callback(process)
            except Exception as e:
                logger.warning(f"Error in process_callback: {e}")

        # Wait for completion with timeout
        stdout, stderr = process.communicate(timeout=timeout_seconds)

        # Log stderr (device/error lines at INFO, the rest at DEBUG)
        _log_service_stderr(stderr)

        # Check exit code
        if process.returncode != 0:
            # Non-zero exit: the service reported failure via an error JSON.
            try:
                error_data = _parse_service_json(stdout, what="error")
            except BeatServiceError:
                raise BeatServiceError(
                    f"Beat service failed with code {process.returncode}: {stderr or stdout}"
                )
            error_type = error_data.get("error", "UnknownError")
            error_msg = error_data.get("message", "Unknown error")
            details = error_data.get("details") or {}
            reason = details.get("reason") or details.get("auto_reason")
            suffix = f" ({reason})" if reason else ""
            raise BeatServiceError(f"{error_type}: {error_msg}{suffix}")

        # Parse JSON output
        data = _parse_service_json(stdout, what="result")

        # Convert to dataclasses
        beats = [
            Beat(
                time=b["time"],
                index=b["index"],
                bar=b.get("bar"),
                beat_in_bar=b.get("beat_in_bar"),
            )
            for b in data.get("beats", [])
        ]

        downbeats = [
            Downbeat(
                time=d["time"],
                bar=d["bar"],
            )
            for d in data.get("downbeats", [])
        ]

        result = BeatAnalysisResult(
            tempo=data["tempo"],
            tempo_confidence=data.get("tempo_confidence", 0.0),
            time_signature=data.get("time_signature", "4/4"),
            beats=beats,
            downbeats=downbeats,
            analysis_duration=data.get("analysis_duration", 0.0),
            audio_duration=data.get("audio_duration"),
            backend=data.get("backend") or resolved_device,
            warnings=data.get("warnings", []),
        )

        logger.info(
            f"Beat analysis complete: {result.tempo:.1f} BPM, "
            f"{len(beats)} beats, {len(downbeats)} downbeats "
            f"({result.analysis_duration:.1f}s on {result.backend})"
        )

        return result

    except subprocess.TimeoutExpired:
        # Kill process on timeout
        if process:
            _terminate_process(process)
        raise BeatServiceTimeout(f"Beat analysis timed out after {timeout_seconds}s")

    except BeatServiceError:
        raise

    except Exception as e:
        if process and process.poll() is None:
            _terminate_process(process)
        raise BeatServiceError(f"Unexpected error: {e}")
