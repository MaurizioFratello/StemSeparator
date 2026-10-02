"""Root conftest: host-only development shims (imported before any test module).

WHY this exists: the development host has no root/sudo, so PortAudio cannot be
installed system-wide, yet `import sounddevice` fails without a discoverable
libportaudio — and several tests patch `sounddevice.*`, which forces the real
import. When a locally extracted copy exists (recipe in `.planning/PORT_STATE.md`:
`apt-get download libportaudio2 && dpkg -x *.deb /tmp/pa/root`), point ctypes at
it before anything imports sounddevice.

Deliberately a no-op in the normal cases:
- Windows/macOS: skipped outright (PortAudio is a regular system dependency).
- CI Linux job: `apt-get install libportaudio2` makes `find_library` succeed,
  so the shim never engages.
- No local copy at /tmp/pa: the suite fails loudly on the audio tests, which is
  the honest behaviour rather than a silent skip.
"""

import ctypes.util
import os
import sys

_PA_CANDIDATES = (
    # durable copy first (`apt-get download libportaudio2 && dpkg -x` into
    # `~/.local/share/stemsep-dev/lib`, see .planning/PORT_STATE.md) so a /tmp
    # sweep cannot silently downgrade the audio tests again; the /tmp path is
    # the documented one-off location and stays as fallback.
    os.path.expanduser("~/.local/share/stemsep-dev/lib/libportaudio.so.2"),
    "/tmp/pa/root/usr/lib/x86_64-linux-gnu/libportaudio.so.2",
)
_PA_NAMES = ("portaudio", "libportaudio.so.2", "libportaudio")


def _install_portaudio_shim() -> None:
    if sys.platform != "linux":
        return
    if ctypes.util.find_library("portaudio"):
        return  # system PortAudio present — nothing to shim
    for candidate in _PA_CANDIDATES:
        if os.path.exists(candidate):
            real = ctypes.util.find_library

            def _patched(name, _c=candidate, _real=real):
                return _c if name in _PA_NAMES else _real(name)

            ctypes.util.find_library = _patched
            return


_install_portaudio_shim()
