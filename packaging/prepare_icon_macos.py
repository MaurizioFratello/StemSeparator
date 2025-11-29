#!/usr/bin/env python3
"""
Prepare Icon_V1.png for macOS standards

Crops/resizes the icon to 1024x1024 with rounded corners (macOS style).
"""
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    print("ERROR: Pillow not installed. Install with: pip install Pillow")
    sys.exit(1)

# macOS icon standards
ICON_SIZE = 1024
CORNER_RADIUS = int(ICON_SIZE * 0.2)  # 20% for rounded corners


def create_rounded_mask(size: int, radius: int) -> Image.Image:
    """Create a rounded rectangle mask"""
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    
    # Draw rounded rectangle
    draw.rounded_rectangle(
        [(0, 0), (size, size)],
        radius=radius,
        fill=255
    )
    
    return mask


def prepare_icon(input_path: Path, output_path: Path, size: int = ICON_SIZE):
    """
    Prepare icon for macOS: resize, crop, add rounded corners
    
    Args:
        input_path: Path to source icon
        output_path: Path to save processed icon
        size: Target size (default 1024)
    """
    print(f"Loading icon: {input_path}")
    
    # Load image
    img = Image.open(input_path)
    original_size = img.size
    print(f"  Original size: {original_size[0]}x{original_size[1]}")
    
    # Convert to RGBA if needed
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Calculate crop/resize
    # Maintain aspect ratio, center crop
    aspect_ratio = original_size[0] / original_size[1]
    
    if aspect_ratio > 1:
        # Wider than tall - crop width
        new_width = int(original_size[1] * 1.0)
        new_height = original_size[1]
        left = (original_size[0] - new_width) // 2
        top = 0
        right = left + new_width
        bottom = new_height
    elif aspect_ratio < 1:
        # Taller than wide - crop height
        new_width = original_size[0]
        new_height = int(original_size[0] / 1.0)
        left = 0
        top = (original_size[1] - new_height) // 2
        right = new_width
        bottom = top + new_height
    else:
        # Square - use as is
        left = 0
        top = 0
        right = original_size[0]
        bottom = original_size[1]
    
    # Crop to square
    if aspect_ratio != 1:
        print(f"  Cropping to square: {new_width}x{new_height}")
        img = img.crop((left, top, right, bottom))
    
    # Resize to target size
    print(f"  Resizing to {size}x{size}")
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    
    # Create rounded corners mask
    print(f"  Adding rounded corners (radius: {CORNER_RADIUS}px)")
    mask = create_rounded_mask(size, CORNER_RADIUS)
    
    # Apply mask
    output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    output.paste(img, (0, 0))
    output.putalpha(mask)
    
    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_path, 'PNG', optimize=True)
    
    print(f"✓ Icon prepared: {output_path}")
    print(f"  Size: {size}x{size} pixels")
    print(f"  Format: PNG with alpha channel")


def main():
    """Main entry point"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    input_path = project_root / "resources" / "icons" / "Icon_V1.png"
    output_path = project_root / "resources" / "icons" / "app_icon_1024.png"
    
    if not input_path.exists():
        print(f"ERROR: Icon not found: {input_path}")
        sys.exit(1)
    
    print("Preparing Icon_V1.png for macOS...")
    print()
    
    prepare_icon(input_path, output_path)
    
    print()
    print("Next step: Create .icns file")
    print("  Run: python packaging/create_icns.py")


if __name__ == "__main__":
    main()

