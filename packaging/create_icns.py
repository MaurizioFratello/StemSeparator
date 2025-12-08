#!/usr/bin/env python3
"""
Create .icns file from 1024x1024 PNG icon

Uses macOS iconutil to create a proper .icns file with all required sizes.
"""
import subprocess
import sys
from pathlib import Path


def create_icns(png_path: Path, output_icns: Path = None):
    """
    Create .icns file from PNG using macOS iconutil

    Args:
        png_path: Path to 1024x1024 PNG icon
        output_icns: Output path for .icns file (default: same dir as PNG)
    """
    if not png_path.exists():
        print(f"ERROR: PNG file not found: {png_path}")
        sys.exit(1)

    if output_icns is None:
        output_icns = png_path.parent / "app_icon.icns"

    # Create temporary iconset directory
    iconset_dir = png_path.parent / "icon.iconset"
    iconset_dir.mkdir(exist_ok=True)

    print(f"Creating iconset from: {png_path}")
    print(f"Output: {output_icns}")
    print()

    # Create all required sizes using sips (macOS built-in)
    sizes = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]

    for size, filename in sizes:
        output_file = iconset_dir / filename
        try:
            subprocess.run(
                [
                    "sips",
                    "-z",
                    str(size),
                    str(size),
                    str(png_path),
                    "--out",
                    str(output_file),
                ],
                check=True,
                capture_output=True,
            )
            print(f"  ✓ Created {filename} ({size}x{size})")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Failed to create {filename}: {e}")
            sys.exit(1)
        except FileNotFoundError:
            print("ERROR: 'sips' command not found. This script requires macOS.")
            sys.exit(1)

    # Convert iconset to .icns
    print()
    print("Converting iconset to .icns...")
    try:
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(output_icns)],
            check=True,
            capture_output=True,
        )
        print(f"✓ Created .icns file: {output_icns}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create .icns: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: 'iconutil' command not found. This script requires macOS.")
        sys.exit(1)

    # Clean up iconset directory
    import shutil

    shutil.rmtree(iconset_dir)
    print(f"✓ Cleaned up temporary iconset directory")

    print()
    print("Icon ready for use!")
    print(f"  PNG: {png_path}")
    print(f"  ICNS: {output_icns}")


def main():
    """Main entry point"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    png_path = project_root / "resources" / "icons" / "app_icon_1024.png"

    if not png_path.exists():
        print(f"ERROR: Icon PNG not found: {png_path}")
        print("Please run: python packaging/generate_icon.py first")
        sys.exit(1)

    create_icns(png_path)


if __name__ == "__main__":
    main()
