#!/usr/bin/env python3
"""
Generate Stem Separator App Icon

Creates a 1024x1024 PNG icon with a waveform splitting into stems,
using the app's purple-blue gradient theme.
"""
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
    import numpy as np
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Please install: pip install Pillow numpy")
    sys.exit(1)

# App theme colors
ACCENT_PRIMARY = "#667eea"      # Purple-blue
ACCENT_SECONDARY = "#764ba2"   # Purple
BACKGROUND = "#1e1e1e"         # Dark background

def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_icon(output_path: Path, size: int = 1024):
    """
    Create app icon with waveform splitting into stems
    
    Args:
        output_path: Path to save the icon
        size: Icon size in pixels (default 1024)
    """
    # Create image with rounded corners (macOS style)
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # macOS icon has rounded corners - create rounded rectangle mask
    corner_radius = int(size * 0.2)  # 20% of size for rounded corners
    
    # Draw rounded rectangle background
    def rounded_rectangle(xy, radius, fill):
        """Draw rounded rectangle"""
        x1, y1, x2, y2 = xy
        # Draw main rectangle
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        # Draw corners
        draw.ellipse([x1, y1, x1 + 2*radius, y1 + 2*radius], fill=fill)
        draw.ellipse([x2 - 2*radius, y1, x2, y1 + 2*radius], fill=fill)
        draw.ellipse([x1, y2 - 2*radius, x1 + 2*radius, y2], fill=fill)
        draw.ellipse([x2 - 2*radius, y2 - 2*radius, x2, y2], fill=fill)
    
    # Background with subtle gradient
    bg_color = hex_to_rgb(BACKGROUND)
    rounded_rectangle([0, 0, size, size], corner_radius, bg_color)
    
    # Create gradient from primary to secondary accent
    primary_rgb = hex_to_rgb(ACCENT_PRIMARY)
    secondary_rgb = hex_to_rgb(ACCENT_SECONDARY)
    
    # Draw waveform that splits into stems
    center_y = size // 2
    wave_width = int(size * 0.7)  # 70% of icon width
    wave_height = int(size * 0.3)  # 30% of icon height
    start_x = (size - wave_width) // 2
    
    # Main waveform (left side - single wave)
    num_points = 50
    points_main = []
    for i in range(num_points // 2):
        x = start_x + (i / (num_points // 2)) * (wave_width * 0.4)
        # Sine wave with varying amplitude
        amplitude = wave_height * 0.5 * (1 + 0.3 * np.sin(i * 0.3))
        y = center_y + amplitude * np.sin(i * 0.5)
        points_main.append((x, y))
    
    # Split point
    split_x = start_x + wave_width * 0.4
    
    # Stem 1 (top) - continues from main wave
    points_stem1 = []
    for i in range(num_points // 2):
        x = split_x + (i / (num_points // 2)) * (wave_width * 0.6)
        # Waveform with different frequency
        amplitude = wave_height * 0.4 * (1 + 0.2 * np.sin(i * 0.4))
        y = center_y - wave_height * 0.3 + amplitude * np.sin(i * 0.6)
        points_stem1.append((x, y))
    
    # Stem 2 (middle) - continues from main wave
    points_stem2 = []
    for i in range(num_points // 2):
        x = split_x + (i / (num_points // 2)) * (wave_width * 0.6)
        amplitude = wave_height * 0.35 * (1 + 0.25 * np.sin(i * 0.35))
        y = center_y + amplitude * np.sin(i * 0.55)
        points_stem2.append((x, y))
    
    # Stem 3 (bottom) - continues from main wave
    points_stem3 = []
    for i in range(num_points // 2):
        x = split_x + (i / (num_points // 2)) * (wave_width * 0.6)
        amplitude = wave_height * 0.4 * (1 + 0.2 * np.sin(i * 0.45))
        y = center_y + wave_height * 0.3 + amplitude * np.sin(i * 0.65)
        points_stem3.append((x, y))
    
    # Draw waveforms with gradient
    line_width = max(3, int(size * 0.008))  # Responsive line width
    
    # Main waveform (gradient from primary to middle)
    all_points = points_main + [(split_x, center_y)]
    for i in range(len(all_points) - 1):
        # Interpolate color
        t = i / len(all_points)
        r = int(primary_rgb[0] * (1 - t) + secondary_rgb[0] * t)
        g = int(primary_rgb[1] * (1 - t) + secondary_rgb[1] * t)
        b = int(primary_rgb[2] * (1 - t) + secondary_rgb[2] * t)
        color = (r, g, b, 255)
        draw.line([all_points[i], all_points[i+1]], fill=color, width=line_width)
    
    # Stem 1 (top) - gradient to secondary
    all_points_stem1 = [(split_x, center_y)] + points_stem1
    for i in range(len(all_points_stem1) - 1):
        t = i / len(all_points_stem1)
        r = int(primary_rgb[0] * (1 - t) + secondary_rgb[0] * t)
        g = int(primary_rgb[1] * (1 - t) + secondary_rgb[1] * t)
        b = int(primary_rgb[2] * (1 - t) + secondary_rgb[2] * t)
        color = (r, g, b, 255)
        draw.line([all_points_stem1[i], all_points_stem1[i+1]], fill=color, width=line_width)
    
    # Stem 2 (middle) - gradient to secondary
    all_points_stem2 = [(split_x, center_y)] + points_stem2
    for i in range(len(all_points_stem2) - 1):
        t = i / len(all_points_stem2)
        r = int(primary_rgb[0] * (1 - t) + secondary_rgb[0] * t)
        g = int(primary_rgb[1] * (1 - t) + secondary_rgb[1] * t)
        b = int(primary_rgb[2] * (1 - t) + secondary_rgb[2] * t)
        color = (r, g, b, 255)
        draw.line([all_points_stem2[i], all_points_stem2[i+1]], fill=color, width=line_width)
    
    # Stem 3 (bottom) - gradient to secondary
    all_points_stem3 = [(split_x, center_y)] + points_stem3
    for i in range(len(all_points_stem3) - 1):
        t = i / len(all_points_stem3)
        r = int(primary_rgb[0] * (1 - t) + secondary_rgb[0] * t)
        g = int(primary_rgb[1] * (1 - t) + secondary_rgb[1] * t)
        b = int(primary_rgb[2] * (1 - t) + secondary_rgb[2] * t)
        color = (r, g, b, 255)
        draw.line([all_points_stem3[i], all_points_stem3[i+1]], fill=color, width=line_width)
    
    # Add subtle glow effect
    img_with_glow = img.filter(ImageFilter.GaussianBlur(radius=size * 0.01))
    img = Image.alpha_composite(img_with_glow, img)
    
    # Save icon
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, 'PNG', optimize=True)
    print(f"✓ Icon created: {output_path}")
    print(f"  Size: {size}x{size} pixels")
    print(f"  Colors: {ACCENT_PRIMARY} → {ACCENT_SECONDARY}")


def main():
    """Main entry point"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Output paths
    icons_dir = project_root / "resources" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)
    
    output_png = icons_dir / "app_icon_1024.png"
    
    print("Generating Stem Separator app icon...")
    print(f"Output: {output_png}")
    print()
    
    create_icon(output_png, size=1024)
    
    print()
    print("Next steps:")
    print("1. Review the icon at:", output_png)
    print("2. To create .icns file, run:")
    print("   python packaging/create_icns.py")
    print("   (or use iconutil manually)")


if __name__ == "__main__":
    main()

