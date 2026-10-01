"""
PyAudio shim for the BeatNet beat-service

PURPOSE: make ``import pyaudio`` inside BeatNet succeed in the headless service.

CONTEXT: ``BeatNet/BeatNet.py`` imports ``pyaudio`` at *module* scope, so the
         dependency is unavoidable even though the service always runs
         ``mode="offline"``. PyAudio itself is only touched when
         ``BeatNet.__init__`` builds a microphone stream, which happens solely
         for ``mode="stream"``/``"realtime"`` - a code path this service never
         selects (``src/__main__.py`` hard-codes ``mode="offline"``).

The previous version of this file was an unconditional no-op mock justified by
"PyInstaller on macOS does not ship PyAudio". That reasoning is only true on
one platform and was never checked: ``pyaudio`` is in
``packaging/beatnet_service/build.sh`` and pip wheels for Windows/macOS bundle
PortAudio, so on those machines the *real* module was silently replaced by a
fake that cannot open a stream. The shim is therefore conditional now:

1. **Real PyAudio** - if the genuine package imports (after pre-loading the
   PortAudio/ALSA shared libraries that the extension needs but does not
   declare), every public name is re-exported and nothing is mocked.
2. **Offline stub** - otherwise BeatNet gets the constants plus a ``PyAudio``
   whose ``open()`` raises a ``RuntimeError`` that names the missing library
   and the platform-specific fix. Offline analysis is unaffected because it
   never opens a stream; ``REALTIME_SUPPORTED`` and ``OFFLINE_REASON`` record
   which tier is active for logs and diagnostics.
"""

from __future__ import annotations

import contextlib
import ctypes
import ctypes.util
import importlib
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Marker so the loader can recognise this file even if it is imported twice
# (once as `pyaudio` from the frozen bundle, once as `src.pyaudio`).
_IS_BEATNET_SERVICE_STUB = True

TOP_LEVEL_NAME = "pyaudio"

# Set by :func:`ensure_available` / the import-time probe.
REALTIME_SUPPORTED = False
OFFLINE_REASON: Optional[str] = None
_PROBED = False

# Environment override for environments where PortAudio lives outside the
# default loader search (containers, vendored builds, macOS CI runners).
PORTAUDIO_ENV_VAR = "STEMSEPARATOR_PORTAUDIO_LIBRARY"

# Shared libraries the CPython PyAudio extension needs in the global symbol
# namespace. WHY: the manylinux wheel links `pyaudio._portaudio` against
# PortAudio/ALSA but records neither as a needed library, so `dlopen` fails
# with `undefined symbol: snd_pcm_hw_params_any` (or a `pa_*` symbol) unless
# they are loaded first. The macOS and Windows wheels bundle PortAudio inside
# the extension, so the probe is restricted to the systems that need it.
_IS_POSIX_WITH_ALSA = sys.platform.startswith(("linux", "freebsd"))
_PRELOAD_CANDIDATES: Tuple[Tuple[str, ...], ...] = (
    (("portaudio", "libportaudio.so.2"), ("asound", "libasound.so.2"))
    if _IS_POSIX_WITH_ALSA
    else ()
)


def _preload_portaudio() -> Tuple[List[str], List[str]]:
    """
    Load PortAudio (and ALSA) into the global symbol namespace.

    Returns:
        ``(loaded, failed)`` lists of the attempted library paths.
    """
    loaded: List[str] = []
    failed: List[str] = []

    attempts: List[str] = []
    override = os.environ.get(PORTAUDIO_ENV_VAR)
    if override:
        attempts.append(override)
    # WHY additive: pointing at a vendored libportaudio does not remove the
    # need for ALSA on Linux, so the discovered candidates are always tried
    # too instead of replacing them.
    for names in _PRELOAD_CANDIDATES:
        for name in names:
            resolved = ctypes.util.find_library(name)
            for candidate in (resolved, name):
                if candidate and candidate not in attempts:
                    attempts.append(candidate)
                    break

    for path in attempts:
        try:
            ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
            loaded.append(path)
        except OSError as exc:
            # Keep the message short; the full list is only interesting when
            # someone wonders why tier 1 was skipped.
            failed.append(f"{path} ({exc.__class__.__name__})")
    return loaded, failed


def _normalised(path: str) -> str:
    try:
        return str(Path(path).resolve())
    except OSError:  # pragma: no cover - unreadable sys.path entries
        return str(path)


_THIS_DIR = _normalised(str(Path(__file__).resolve().parent))
_PROBE_IN_PROGRESS = False

# What the shared-library pre-load achieved; the CLI logs it so a "why is
# PyAudio mocked on this machine" question can be answered from the app log.
PRELOAD_LOADED: List[str] = []
PRELOAD_FAILED: List[str] = []


def _import_real_pyaudio() -> Tuple[Optional[object], Optional[str]]:
    """
    Import the genuine ``pyaudio`` package, bypassing this file.

    Returns:
        ``(module, error)`` - exactly one of them is ``None``.

    WHY the path surgery: the frozen service binary puts ``src/`` on
         ``sys.path``, so a plain ``importlib.import_module("pyaudio")`` from
         inside this module resolves back to the stub. Dropping our own
         directory (and our half-initialised ``sys.modules`` entry) lets the
         import system find the real package in site-packages or the bundle,
         and everything is restored afterwards so BeatNet keeps importing the
         name it expects.
    """
    global _PROBE_IN_PROGRESS
    if _PROBE_IN_PROGRESS:
        return None, "recursive probe aborted"
    _PROBE_IN_PROGRESS = True

    previous = sys.modules.pop(TOP_LEVEL_NAME, None)
    saved_path = list(sys.path)
    sys.path[:] = [p for p in saved_path if _normalised(p) != _THIS_DIR]
    try:
        loaded, failed = _preload_portaudio()
        PRELOAD_LOADED.extend(loaded)
        PRELOAD_FAILED.extend(failed)
        # WHY the redirect: PyAudio reports a broken C extension with a bare
        # `print()` - i.e. on *stdout*, which is this service's JSON channel.
        # Anything the import says out loud is rerouted to stderr instead.
        with contextlib.redirect_stdout(sys.stderr):
            module = importlib.import_module(TOP_LEVEL_NAME)
        if (
            module is previous
            or getattr(module, "_IS_BEATNET_SERVICE_STUB", False)
            or not hasattr(module, "PyAudio")
            or not hasattr(module, "paFloat32")
        ):
            return None, "no usable PyAudio implementation found"
        return module, None
    except BaseException as exc:  # noqa: BLE001 - any failure means "use stub"
        return None, f"{type(exc).__name__}: {exc}"
    finally:
        sys.path[:] = saved_path
        sys.modules.pop(TOP_LEVEL_NAME, None)
        if previous is not None:
            sys.modules[TOP_LEVEL_NAME] = previous
        _PROBE_IN_PROGRESS = False


# ---------------------------------------------------------------------------
# Offline stub (tier 2)
# ---------------------------------------------------------------------------

# Sample-format constants mirror portaudio's own values, so a caller that
# builds a stream descriptor cannot tell the two tiers apart.
paFloat32 = 1
paInt32 = 2
paInt24 = 4
paInt16 = 8
paContinue = 0
paComplete = 1
paAbort = 2


class PyAudio:
    """
    Offline replacement for ``pyaudio.PyAudio`` - no device I/O.

    Only instantiated by BeatNet when ``mode`` is ``stream``/``realtime``;
    ``open()`` therefore fails loudly instead of pretending to capture audio.
    """

    def __init__(self, *args, **kwargs):
        pass

    def open(self, *args, **kwargs):
        raise RuntimeError(
            "BeatNet beat-service is offline-only and PyAudio is unavailable: "
            f"{OFFLINE_REASON or 'real PyAudio could not be imported'}. "
            "Install PortAudio for realtime capture "
            "(macOS: `brew install portaudio && pip install pyaudio`, "
            "Linux: `apt-get install libportaudio2 libasound2`, "
            "Windows: the PyAudio wheel bundles PortAudio), or analyse from a "
            f"file as this service does. Set {PORTAUDIO_ENV_VAR} to point at a "
            "specific libportaudio shared library."
        )

    def terminate(self):
        pass

    def get_device_count(self):
        return 0


def _adopt_real(module: object) -> None:
    """Copy every public name of the real module onto this shim."""
    for attribute in dir(module):
        if attribute.startswith("__"):
            continue
        try:
            setattr(sys.modules[__name__], attribute, getattr(module, attribute))
        except (AttributeError, KeyError):  # pragma: no cover - exotic objects
            continue


def _adopt(module: Optional[object], error: Optional[str]) -> None:
    """Install the outcome of a real-PyAudio probe as this module's state."""
    global REALTIME_SUPPORTED, OFFLINE_REASON
    if module is not None:
        _adopt_real(module)
        REALTIME_SUPPORTED = True
        OFFLINE_REASON = None
    else:
        OFFLINE_REASON = error


def ensure_available(force_stub: bool = False) -> str:
    """
    Make ``import pyaudio`` inside BeatNet resolve to something usable.

    Args:
        force_stub: skip the real-import attempt (used when the caller already
            knows PortAudio is absent and wants the documented stub error).

    Returns:
        ``"real"`` or ``"stub"``, for the CLI's log line.
    """
    global _PROBED

    if not _PROBED and not force_stub:
        _PROBED = True
        _adopt(*_import_real_pyaudio())

    # BeatNet imports the plain name; register ourselves under it so the
    # resolution does not depend on whether site-packages has a working build.
    this_module = sys.modules.get(__name__) or sys.modules.get(TOP_LEVEL_NAME)
    if this_module is not None:
        sys.modules[TOP_LEVEL_NAME] = this_module

    return "real" if REALTIME_SUPPORTED else "stub"


def describe() -> str:
    """
    One-line PyAudio status for the CLI's stderr log.

    WHY it includes the pre-load result: "PortAudio is installed but not where
    the loader looks for it" is the usual reason tier 1 was skipped, and the
    library paths are exactly what an operator has to fix.
    """
    if REALTIME_SUPPORTED:
        return "pyaudio: real PyAudio in use"
    text = f"pyaudio: offline stub ({OFFLINE_REASON})"
    if PRELOAD_LOADED:
        text += f" [preloaded: {', '.join(PRELOAD_LOADED)}]"
    if PRELOAD_FAILED:
        text += f" [preload failed: {', '.join(PRELOAD_FAILED)}]"
    return text


# Importing the module is enough for the frozen binary (where this file *is*
# `pyaudio`); `ensure_available()` additionally rebinds the name for source
# runs, where the package is `src.pyaudio` and BeatNet still asks for
# `pyaudio`.
_adopt(*_import_real_pyaudio())
