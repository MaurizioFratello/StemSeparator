"""PyInstaller runtime hook for the frozen Linux build.

Registered by ``packaging/linux/StemSeparator-linux.spec`` via ``runtime_hooks``.
Runs before ``main.py`` (see PKG-04 in ``docs/PACKAGING.md``).

Why the two patches below exist:

* Library search paths -- ``utils.platform_utils.configure_native_library_dirs``
  makes ``torch/lib`` and the collected ``nvidia/*/lib`` directories resolvable
  before the first heavy import. The macOS build gets the equivalent from
  ``DYLD_LIBRARY_PATH`` in ``packaging/build_arm64.sh``; on Linux the bootloader
  only puts ``_internal`` itself on ``LD_LIBRARY_PATH``, not its subdirectories.

* PortAudio discovery -- ``sounddevice`` locates PortAudio through
  ``ctypes.util.find_library('portaudio')``. On POSIX that helper asks ``gcc
  -Wl,-t`` and ``ldconfig -p``, neither of which knows about a library shipped
  inside the bundle: ``LD_LIBRARY_PATH`` is ignored by both, so the vendored
  ``_internal/libportaudio.so.2`` is invisible and ``import sounddevice`` fails
  with ``OSError: PortAudio library not found``. Patching the lookup here is the
  only deterministic fix; the system library still wins when it is resolvable,
  which keeps the PipeWire/ALSA-backed host build in charge when present.
"""

import os
import sys


def _pyi_rthook():
    if sys.platform != "linux" or not getattr(sys, "frozen", False):
        return

    def log_failure(context, exc):
        """Persist a hook failure; windowed builds have no usable stderr."""
        try:
            with open(os.path.join(sys._MEIPASS, "_rthook-linux-error.log"), "a", encoding="utf-8") as handle:
                handle.write(f"{context}: {type(exc).__name__}: {exc}\n")
        except OSError:
            pass

    # --- native library search path ---------------------------------------
    try:
        from utils.platform_utils import (
            configure_native_library_dirs,
            ensure_binaries_on_path,
            torch_library_dirs,
        )

        configure_native_library_dirs(torch_library_dirs())
        ensure_binaries_on_path()
    except Exception as exc:  # pragma: no cover - build-time diagnosis
        log_failure("native library path setup failed", exc)

    # --- PortAudio discovery ----------------------------------------------
    try:
        import ctypes.util
        from pathlib import Path

        root = Path(sys._MEIPASS)
        names = ("portaudio", "libportaudio", "libportaudio.so", "libportaudio.so.2")
        candidates = [root / "libportaudio.so.2", root / "libportaudio.so.2.0.0"]
        bundled = next((str(path) for path in candidates if path.exists()), None)

        if bundled is not None:
            original = ctypes.util.find_library

            def find_library(name, _orig=original, _bundled=bundled, _names=names):
                found = _orig(name)
                if found:
                    return found
                if name in _names:
                    return _bundled
                return None

            ctypes.util.find_library = find_library
    except Exception as exc:  # pragma: no cover - build-time diagnosis
        log_failure("PortAudio discovery patch failed", exc)


_pyi_rthook()
