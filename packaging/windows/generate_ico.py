#!/usr/bin/env python3
"""
Generate the Windows application icon (packaging/windows/StemSeparator.ico).

Usage (any OS, from the repository root):

    python packaging/windows/generate_ico.py

WHY a generator instead of a committed blob: the .ico must stay in step with the
master artwork (`resources/icons/app_icon_1024.png`), and Windows wants several
bitmaps in one container. Pillow writes the container, so the repo keeps the
single source PNG plus this script; rerun it after any artwork change.

The size set is the conventional one for desktop apps: Explorer, the taskbar,
the Alt-Tab strip, Control Panel / Add-Remove Programs and the high-DPI
variants. Sizes above 256 are invalid in an .ico entry header, so 256 is the
top rung (Windows composes larger icons from it).
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - build-time dependency
    sys.exit("Pillow is required: pip install -r requirements-build.txt")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PNG = PROJECT_ROOT / "resources" / "icons" / "app_icon_1024.png"
OUTPUT_ICO = Path(__file__).resolve().parent / "StemSeparator.ico"

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def build(source: Path = SOURCE_PNG, target: Path = OUTPUT_ICO) -> Path:
    """Write `target` as a multi-size .ico built from the master `source` PNG."""
    if not source.is_file():
        sys.exit(f"master artwork missing: {source}")

    with Image.open(source) as master:
        if master.width != master.height:
            sys.exit(
                f"{source} is {master.width}x{master.height}; the .ico ladder needs a square master"
            )
        image = master.convert("RGBA")
        # Downscale with the high-quality resampler: the small rungs of the
        # ladder are what users actually see in the taskbar.
        image.thumbnail((256, 256), Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, format="ICO", sizes=[(size, size) for size in ICO_SIZES])

    return target


def verify(target: Path = OUTPUT_ICO) -> list[tuple[int, int]]:
    """Reopen the container and return the sizes it really holds."""
    with Image.open(target) as ico:
        if ico.format != "ICO":
            sys.exit(f"{target} was not written as an ICO ({ico.format})")
        return sorted(ico.info.get("sizes") or {ico.size})


if __name__ == "__main__":
    path = build()
    sizes = verify(path)
    print(f"wrote {path} ({path.stat().st_size} bytes)")
    print("sizes: " + ", ".join(f"{w}x{h}" for w, h in sizes))
    missing = [s for s in ICO_SIZES if (s, s) not in sizes]
    if missing:
        sys.exit(f"ICO is missing sizes: {missing}")
