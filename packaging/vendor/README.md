# Vendored native binaries

Everything in this directory **except this file and `fetch_vendor.py` is
gitignored**. The Linux and Windows builds bundle FFmpeg, and the Linux build
additionally bundles PortAudio, so users never have to install anything by hand
and a build does not depend on whatever happens to be on the machine that runs
it. On a clean checkout, reproduce the tree byte-for-byte with:

```bash
PY=python3.11                                    # the interpreter you build with
$PY packaging/vendor/fetch_vendor.py --platform linux     # Linux build inputs
$PY packaging/vendor/fetch_vendor.py --platform windows   # Windows build inputs
$PY packaging/vendor/fetch_vendor.py --check --platform all   # verify, no writes
```

`fetch_vendor.py` is stdlib-only, downloads over HTTPS, verifies SHA-256 for the
whole archive **and** for every extracted file, writes atomically (`.part` +
`os.replace`) and exits non-zero on any mismatch. Files that are already present
with the right checksum are not re-downloaded; `--force` rewrites everything.

No `sudo`: the script never calls `dpkg-deb`, `ar` or `tar`; the `.deb`, `.tar.xz`
and `.zip` containers are parsed in Python. Extracting the Ubuntu PortAudio deb
needs a zstd decompressor, because that member is stored as `data.tar.zst` — the
script uses the `zstd` CLI if present, otherwise the `zstandard` Python module
(`uv pip install --python $PY zstandard`), and fails with an explicit message
when neither is available.

## Layout and who consumes it

| Gitignored path | Consumed by |
| --------------- | ----------- |
| `linux/bin/ffmpeg`, `linux/bin/ffprobe` | `packaging/linux/StemSeparator-linux.spec` → `_internal/bin/` |
| `linux/native/libportaudio.so.2` (SONAME symlink) + `libportaudio.so.2.0.0` | same spec → `_internal/`, resolved by `packaging/linux/_pyi_rthook_linux.py` |
| `linux/GPLv3.txt` | provenance record for the GPL build |
| `windows/bin/ffmpeg.exe`, `windows/bin/ffprobe.exe` | `packaging/windows/StemSeparator-win.spec` → `_internal/bin/` |
| `windows/GPLv3.txt` | provenance record for the GPL build |

Putting the tools in `_internal/bin` is not an invention of this file:
`utils.platform_utils.bundled_binary_dirs()` probes `<bundle>/bin` first, and the
Windows spec also accepts the unpacked archive in place, since
`utils.platform_utils.FFMPEG_WINDOWS_DIRNAME` (the directory BtbN's zip extracts
to) is probed as well.

For a **development** checkout, `bundled_binary_dirs()` additionally probes
`packaging/vendor/bin`; the fetch script does not manage that directory, so link
the vendored tools in if you want `python main.py` to use them:

```bash
mkdir -p packaging/vendor/bin
ln -sf ../linux/bin/ffmpeg  packaging/vendor/bin/ffmpeg
ln -sf ../linux/bin/ffprobe packaging/vendor/bin/ffprobe
```

## Provenance (Linux)

Static builds from johnvansickle.com: linked against nothing but the kernel, so
they run on any x86-64 distribution regardless of glibc version.

| File | Source | SHA-256 |
| ---- | ------ | ------- |
| archive | <https://johnvansickle.com/ffmpeg/releases/ffmpeg-7.0.2-amd64-static.tar.xz> (41 888 096 B) | `abda8d77ce8309141f83ab8edf0596834087c52467f6badf376a6a2a4c87cf67` |
| `linux/bin/ffmpeg` | member `ffmpeg-7.0.2-amd64-static/ffmpeg` | `e7e7fb30477f717e6f55f9180a70386c62677ef8a4d4d1a5d948f4098aa3eb99` |
| `linux/bin/ffprobe` | member `ffmpeg-7.0.2-amd64-static/ffprobe` | `4f231a1960d83e403d08f7971e271707bec278a9ae18e21b8b5b03186668450d` |
| `linux/GPLv3.txt` | member `ffmpeg-7.0.2-amd64-static/GPLv3.txt` | `8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903` |
| `linux/native/libportaudio.so.2.0.0` | member `./usr/lib/x86_64-linux-gnu/libportaudio.so.2.0.0` (224 312 B) of `libportaudio2_19.7.0+git20260206.e1b70d33-0ubuntu1_amd64.deb` from <http://de.archive.ubuntu.com/ubuntu/pool/universe/p/portaudio19/> | `38a0eb23ae9468b991d57dab113fd6329b71def164ad61b432fe1178e451608b` |
| whole `.deb` | URL as above | `2c6290fe3730f63569a0f3ee4b24ffcaede479611af608f5f9f643336e0df16d` |

`linux/native/libportaudio.so.2` is a symlink to `libportaudio.so.2.0.0`, which
carries `SONAME libportaudio.so.2`; the fetch script recreates the link. The
package is `portaudio19` version `19.7.0+git20260206.e1b70d33-0ubuntu1`
(`Multi-Arch: same`).

Verified on this build host:

```
$ packaging/vendor/linux/bin/ffmpeg -version | head -1
ffmpeg version 7.0.2-static https://johnvansickle.com/ffmpeg/  Copyright (c) 2000-2024 the FFmpeg developers
$ objdump -p packaging/vendor/linux/bin/ffmpeg | grep -c NEEDED
0                     # fully static: no shared-library dependencies
$ objdump -p packaging/vendor/linux/native/libportaudio.so.2.0.0 | grep -E 'NEEDED|SONAME'
  NEEDED  libasound.so.2
  NEEDED  libjack.so.0
  NEEDED  libpulse.so.0
  NEEDED  libm.so.6
  NEEDED  libc.so.6
  SONAME  libportaudio.so.2
```

**Host prerequisites for the vendored PortAudio:** it links against ALSA, JACK
and PulseAudio, so the target machine needs `libasound.so.2`, `libjack.so.0` and
`libpulse.so.0` (on Ubuntu 24.04+ that is `libasound2t64`,
`libjack-jackd2-0`|`libjack-0.125` and `libpulse0`; PipeWire provides the
PulseAudio one). We ship the library, not its dependencies — the same requirement
the distro package declares. If they are missing, only the `sounddevice`-backed
playback paths are affected; separation and FFmpeg are not.

Why PortAudio is vendored at all: the Linux `sounddevice` wheel carries no
PortAudio copy (the Windows wheel ships `_sounddevice_data/portaudio-binaries/`
`libportaudio64bit.dll`, the macOS one `libportaudio.dylib`), and slim CI or
container images often lack `libportaudio2` entirely. `sounddevice` resolves the
library through `ctypes.util.find_library('portaudio')`, which on POSIX asks only
`gcc -Wl,-t` and `ldconfig -p` — neither sees a file inside the bundle and
`LD_LIBRARY_PATH` is ignored by both — and its `_sounddevice_data` fallback is
Darwin/Windows-only. So on Linux the only deterministic fix is patching the
lookup, which `packaging/linux/_pyi_rthook_linux.py` does; a resolvable system
library keeps priority.

## Provenance (Windows)

FFmpeg from BtbN/FFmpeg-Builds (GPL build; the licence text the archive ships is
vendored as `windows/GPLv3.txt`).

The manifest pins an **immutable** release rather than the moving `latest`
target, so the recorded checksums stay true:

| File | Source | SHA-256 |
| ---- | ------ | ------- |
| archive | <https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-10-01-13-06/ffmpeg-N-127054-g9d3f0f2c58-win64-gpl.zip> | `c1bb626bca84c6f471a04c13a90af68e406c631cf8f9ea2f1a141d4a71adcf52` |
| `windows/bin/ffmpeg.exe` | member `ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe` (168 286 208 B) | `90e7ceda346ac3ff0dab837e863bb2d198309674215614030c3c62b71435cb6e` |
| `windows/bin/ffprobe.exe` | member `ffmpeg-master-latest-win64-gpl/bin/ffprobe.exe` (168 075 264 B) | `b9278f9bb7c296f41bc531c6c4ed88971578a0f27313fd15019e104201803604` |
| `windows/GPLv3.txt` | member `ffmpeg-master-latest-win64-gpl/LICENSE.txt` | `8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903` |

`file` on the extracted binary reports `PE32+ executable (console) x86-64, for MS
Windows`. Members are located by path suffix, so the script is not tied to one
build tag's directory name.

To track the rolling build instead (new checksums every day — never for a
release):

```bash
PY=python3.11
$PY packaging/vendor/fetch_vendor.py --platform windows \
    --windows-tag latest --windows-asset ffmpeg-master-latest-win64-gpl.zip
```

For such an override the pinned hashes no longer apply and the script prints
`no pinned checksum` for the affected files instead of passing silently. Pin tag
and asset together: the asset name embeds the build number, and the two only
match within one release.

## RubberBand (optional, both platforms)

Neither spec vendors `rubberband`. Both look for it in these locations first and
otherwise fall back to the `pyrubberband`/`librosa` time-stretching chain
(`core/time_stretcher.py`), printing a note when it is absent:

* Linux: `packaging/vendor/bin/rubberband`, then `packaging/vendor/linux/bin/rubberband`,
  then `/usr/bin/rubberband` (distro package).
* Windows: `packaging/vendor/windows/bin/rubberband.exe`, then
  `packaging/vendor/windows/rubberband/*/bin/rubberband.exe`.

Build it from source, or on Linux take the distro package (`apt-get download
rubberband-cli` + `dpkg -x` needs no root) and drop the binary into one of those
paths. Per-file checksums apply only to manifest entries, so extra files are
simply not verified. This host has no `rubberband` CLI, and both specs reported
the fallback note during the builds.

## Licences

* The vendored FFmpeg builds are the **GPL** variants; `GPLv3.txt` next to each
  `bin/` is the licence text shipped inside the archive. If the project ever
  switches to the LGPL variants, change the asset names in `fetch_vendor.py` and
  update the tables above.
* PortAudio is distributed under the permissive PortAudio licence; the Ubuntu
  package carries the full text in `usr/share/doc/libportaudio2/copyright`.
* FFmpeg/ffprobe are used as external processes: `audio-separator` shells out to
  them for decoding, and `utils.platform_utils.find_binary()` is what makes them
  findable. Nothing from these archives is linked into the Python process except
  PortAudio, which `sounddevice` loads at runtime.
