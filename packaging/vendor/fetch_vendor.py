#!/usr/bin/env python3
"""
Fetch the third-party binaries the packaging specs expect under packaging/vendor/.

Everything in this directory is gitignored (.gitignore: "Vendored third-party
binaries"); a clean machine reproduces it with this script, which pins exact URLs
and SHA-256 checksums. Read packaging/vendor/README.md for the provenance table.

Usage (from anywhere; needs only the stdlib):

    python packaging/vendor/fetch_vendor.py --platform linux
    python packaging/vendor/fetch_vendor.py --platform windows
    python packaging/vendor/fetch_vendor.py --check

  --check      verify what is already on disk against the manifest, download nothing
  --force      re-download even when the target files already match their checksums
  --dest DIR   write somewhere else (used by CI and by verification runs)
  --windows-tag TAG
               pin a BtbN release tag instead of the mutable `latest`

WHY the downloads are scripted instead of "download by hand from the website":
the specs only print a warning when ffmpeg/ffprobe/libportaudio are missing, and
a warning is far too easy to ignore in release output. A checksummed fetch makes
the input of every build a reviewable line in a file.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

VENDOR_ROOT = Path(__file__).resolve().parent
CHUNK = 1 << 20

# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
# `members` maps an archive member path to its destination relative to
# packaging/vendor/ plus the POSIX mode and the SHA-256 of the *extracted* file
# (what `--check` verifies). An entry-level `sha256` pins the downloaded archive.
# `None` means the upstream artefact is a rolling release and cannot be pinned by
# checksum; pass --windows-tag with an immutable tag to make it reproducible.
MANIFEST: dict[str, dict[str, dict]] = {
    "linux": {
        "ffmpeg-static": {
            "kind": "tar",
            "url": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-7.0.2-amd64-static.tar.xz",
            "sha256": "abda8d77ce8309141f83ab8edf0596834087c52467f6badf376a6a2a4c87cf67",
            "members": {
                "ffmpeg-7.0.2-amd64-static/ffmpeg": {
                    "target": "linux/bin/ffmpeg",
                    "mode": 0o755,
                    "sha256": "e7e7fb30477f717e6f55f9180a70386c62677ef8a4d4d1a5d948f4098aa3eb99",
                },
                "ffmpeg-7.0.2-amd64-static/ffprobe": {
                    "target": "linux/bin/ffprobe",
                    "mode": 0o755,
                    "sha256": "4f231a1960d83e403d08f7971e271707bec278a9ae18e21b8b5b03186668450d",
                },
                "ffmpeg-7.0.2-amd64-static/GPLv3.txt": {
                    "target": "linux/GPLv3.txt",
                    "mode": 0o644,
                    "sha256": "8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903",
                },
            },
        },
        "libportaudio": {
            # Ubuntu 26.04 (resolute) universe, source package portaudio19.
            # The PyPI sounddevice wheel ships no PortAudio binary on Linux and a
            # frozen app must not assume the user has apt access: this is the one
            # library the Linux bundle has to carry for audio I/O.
            "kind": "deb",
            "url": "http://de.archive.ubuntu.com/ubuntu/pool/universe/p/portaudio19/"
            "libportaudio2_19.7.0+git20260206.e1b70d33-0ubuntu1_amd64.deb",
            "sha256": "2c6290fe3730f63569a0f3ee4b24ffcaede479611af608f5f9f643336e0df16d",
            "members": {
                "./usr/lib/x86_64-linux-gnu/libportaudio.so.2.0.0": {
                    "target": "linux/native/libportaudio.so.2.0.0",
                    "mode": 0o644,
                    "sha256": "38a0eb23ae9468b991d57dab113fd6329b71def164ad61b432fe1178e451608b",
                },
            },
            "symlinks": {"linux/native/libportaudio.so.2": "libportaudio.so.2.0.0"},
        },
    },
    "windows": {
        "ffmpeg-win64-gpl": {
            "kind": "zip",
            "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/"
            "{tag}/{asset}",
            "tag": "autobuild-2026-10-01-13-06",
            "asset": "ffmpeg-N-127054-g9d3f0f2c58-win64-gpl.zip",
            # Rolling equivalent (no checksum possible): --windows-tag latest
            # --windows-asset ffmpeg-master-latest-win64-gpl.zip
            "sha256": "c1bb626bca84c6f471a04c13a90af68e406c631cf8f9ea2f1a141d4a71adcf52",
            "members": {
                "bin/ffmpeg.exe": {
                    "target": "windows/bin/ffmpeg.exe",
                    "mode": 0o755,
                    "sha256": "90e7ceda346ac3ff0dab837e863bb2d198309674215614030c3c62b71435cb6e",
                },
                "bin/ffprobe.exe": {
                    "target": "windows/bin/ffprobe.exe",
                    "mode": 0o755,
                    "sha256": "b9278f9bb7c296f41bc531c6c4ed88971578a0f27313fd15019e104201803604",
                },
                "LICENSE.txt": {
                    "target": "windows/GPLv3.txt",
                    "mode": 0o644,
                    "sha256": "8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903",
                },
            },
        },
    },
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, expected_sha256: str | None, label: str) -> bytes:
    """Fetch `url` into memory and fail loudly on checksum drift."""
    print(f"  downloading {label}\n    {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "StemSeparator-fetch_vendor"})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            payload = response.read()
    except (urllib.error.URLError, OSError) as exc:
        raise SystemExit(f"ERROR: could not download {url}: {exc}")

    actual = hashlib.sha256(payload).hexdigest()
    if expected_sha256 is None:
        print(f"    archive has no pinned checksum (rolling tag); got {actual}")
    elif actual != expected_sha256:
        raise SystemExit(
            f"ERROR: checksum mismatch for {label}\n"
            f"    expected {expected_sha256}\n    actual   {actual}\n"
            "Upstream changed. Re-verify provenance before updating the manifest."
        )
    return payload


def open_deb_data(payload: bytes) -> tarfile.TarFile:
    """Open the data archive of a `.deb` without dpkg.

    WHY not `dpkg-deb -x`: builds also run in non-Debian CI images, and a deb is
    a trivial `ar` container - reading it here keeps the fetch script one
    implementation instead of "works unless dpkg is missing".
    """
    rest = payload[len("!<arch>\n"):]
    while rest:
        header, rest = rest[:60], rest[60:]
        if len(header) < 60:
            break
        # dpkg writes the BSD-style ar header: name[0:16] mtime[16:28] uid[28:34]
        # gid[34:40] mode[40:48] size[48:58] fmag[58:60]. Reading the size from
        # the SysV-style offset instead returns the file mode (100644) and turns
        # the extracted body into the following member's header.
        name = header[0:16].decode("ascii", "replace").strip().rstrip("/")
        size = int(header[48:58].decode("ascii").strip())
        body, rest = rest[:size], rest[size:]
        if size % 2:  # ar pads every member to an even byte count
            rest = rest[1:]
        if not name.startswith("data.tar"):
            continue
        if name.endswith(".zst") or name.endswith(".zstd"):
            # Ubuntu 26.04 debs compress the data member with zstd, which
            # tarfile only understands from CPython 3.14 on.
            body = decompress_zstd(body)
        return tarfile.open(fileobj=io.BytesIO(body))
    raise SystemExit("ERROR: deb contains no data.tar member")


def decompress_zstd(blob: bytes) -> bytes:
    """Decompress one zstd frame with the CLI, else the `zstandard` module."""
    zstd = shutil.which("zstd")
    if zstd:
        completed = subprocess.run(
            [zstd, "-d", "-q", "--stdout"], input=blob, stdout=subprocess.PIPE, check=False
        )
        if completed.returncode == 0:
            return completed.stdout
        raise SystemExit(f"ERROR: zstd -d failed with exit code {completed.returncode}")

    try:
        import zstandard
    except ImportError:
        raise SystemExit(
            "ERROR: this deb stores its data member as zstd and neither the `zstd` "
            "binary nor the `zstandard` module is available. Install one of them "
            "(apt-get install zstd / pip install zstandard) and re-run."
        )
    return zstandard.ZstdDecompressor().decompress(blob, max_output_size=64 << 20)



def open_archive(payload: bytes, kind: str):
    if kind == "tar":
        return tarfile.open(fileobj=io.BytesIO(payload))
    if kind == "zip":
        return zipfile.ZipFile(io.BytesIO(payload))
    if kind == "deb":
        return open_deb_data(payload)
    raise SystemExit(f"ERROR: unsupported archive kind {kind!r}")


def resolve_member(archive, suffix: str, kind: str) -> str:
    """Locate an archive member by path suffix.

    WHY suffixes and not full paths: the top-level directory of the BtbN FFmpeg
    zips carries the build identifier (`ffmpeg-master-latest-win64-gpl/`,
    `ffmpeg-N-127054-g9d3f0f2c58-win64-gpl/`), so matching the whole path would
    tie one manifest line to one upstream tag. The shortest match keeps the
    `-shared` documentation copies out of the way.
    """
    names = archive.namelist() if kind == "zip" else archive.getnames()
    matches = [name for name in names if name == suffix or name.endswith("/" + suffix)]
    if not matches:
        raise SystemExit(
            f"ERROR: no member ends with {suffix!r}; the upstream layout changed"
        )
    return min(matches, key=len)


def member_bytes(archive, name: str, kind: str) -> bytes:
    if kind == "zip":
        return archive.read(name)
    handle = archive.extractfile(archive.getmember(name))
    if handle is None:
        raise SystemExit(f"ERROR: {name} is not a regular file in the archive")
    return handle.read()


def write_target(payload: bytes, target: Path, mode: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    if mode is not None and os.name == "posix":
        target.chmod(stat.S_IMODE(mode))
    print(f"    wrote {target.relative_to(VENDOR_ROOT)} ({len(payload)} bytes)")


def check_target(target: Path, expected_sha256: str | None) -> bool:
    label = target.relative_to(VENDOR_ROOT)
    if not target.is_file():
        print(f"  MISSING {label}")
        return False
    actual = sha256_of(target)
    if expected_sha256 is not None and actual != expected_sha256:
        print(
            f"  BAD CHECKSUM {label}\n"
            f"    expected {expected_sha256}\n    actual   {actual}"
        )
        return False
    print(f"  ok {label} ({actual[:12]})")
    return True


def resolve_url(entry: dict, args) -> str:
    """Fill the {tag}/{asset} placeholders of a release-download URL."""
    url = entry["url"]
    if "{tag}" in url or "{asset}" in url:
        return url.format(
            tag=args.windows_tag or entry.get("tag", "latest"),
            asset=args.windows_asset or entry.get("asset", "latest"),
        )
    return url


def fetch_entry(name: str, entry: dict, args) -> bool:
    members = entry["members"]

    # WHY: the manifest checksums describe the pinned tag/asset. A caller who
    # overrode either downloaded something the manifest never described, so only
    # existence is verified then (README: pinned vs rolling Windows builds).
    use_checksums = (
        "{tag}" not in entry["url"]
        or (args.windows_tag is None and args.windows_asset is None)
    )

    def expected(spec: dict) -> str | None:
        return spec["sha256"] if use_checksums else None

    if args.check:
        # list() instead of all(): report every missing file, not just the first.
        return all(
            [
                check_target(VENDOR_ROOT / spec["target"], expected(spec))
                for spec in members.values()
            ]
        )

    if not args.force and all(
        (VENDOR_ROOT / spec["target"]).is_file()
        and (expected(spec) is None or sha256_of(VENDOR_ROOT / spec["target"]) == expected(spec))
        for spec in members.values()
    ):
        print(f"  {name}: already vendored (use --force to re-download)")
        return True

    payload = download(resolve_url(entry, args), entry["sha256"] if use_checksums else None, name)
    archive = open_archive(payload, entry["kind"])
    for suffix, spec in members.items():
        member = resolve_member(archive, suffix, entry["kind"])
        target = VENDOR_ROOT / spec["target"]
        write_target(member_bytes(archive, member, entry["kind"]), target, spec["mode"])
        if expected(spec) is not None and sha256_of(target) != expected(spec):
            raise SystemExit(f"ERROR: extracted {member} does not match its pinned checksum")

    for relative, link_target in entry.get("symlinks", {}).items():
        link = VENDOR_ROOT / relative
        if not link.parent.is_dir():
            continue
        if link.is_symlink() and os.readlink(link) == link_target:
            continue
        if link.exists() or link.is_symlink():
            link.unlink()
        # WHY the SONAME link: ctypes/PortAudio resolve the library by SONAME
        # ("libportaudio.so.2"), so it has to be reachable under that name.
        link.symlink_to(link_target)
        print(f"    linked {link.relative_to(VENDOR_ROOT)} -> {link_target}")
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch the gitignored third-party binaries used by the PyInstaller specs."
    )
    parser.add_argument("--platform", choices=["linux", "windows", "all"], default="all")
    parser.add_argument("--dest", type=Path, default=None, help="override packaging/vendor")
    parser.add_argument("--force", action="store_true", help="re-download pinned artefacts")
    parser.add_argument(
        "--check", action="store_true", help="validate the files on disk, download nothing"
    )
    parser.add_argument(
        "--windows-tag",
        default=None,
        help="BtbN FFmpeg-Builds release tag (default: latest). Use an immutable tag "
        "such as autobuild-2026-10-01-13-06 to make a Windows build reproducible.",
    )
    parser.add_argument(
        "--windows-asset",
        default=None,
        help="asset name inside the BtbN release (default: ffmpeg-master-latest-win64-gpl.zip). "
        "Immutable builds are published as ffmpeg-N-<build>-win64-gpl.zip and must be "
        "requested together with the matching --windows-tag.",
    )
    args = parser.parse_args(argv)

    global VENDOR_ROOT
    if args.dest is not None:
        VENDOR_ROOT = args.dest.resolve()
        VENDOR_ROOT.mkdir(parents=True, exist_ok=True)

    platforms = ["linux", "windows"] if args.platform == "all" else [args.platform]
    ok = True
    for platform in platforms:
        print(f"[{platform}]")
        for name, entry in MANIFEST[platform].items():
            try:
                ok = fetch_entry(name, entry, args) and ok
            except SystemExit as exc:
                print(f"  {name}: {exc}")
                ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
