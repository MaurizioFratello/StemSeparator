# macOS App Icon Guide

This document provides detailed instructions for creating and integrating a macOS app icon for StemSeparator.

## Overview

macOS app icons use the `.icns` format, which contains multiple resolutions of the same icon. This ensures your app looks sharp on all display types (Retina and non-Retina).

## Required Icon Sizes

A complete `.icns` file should include the following sizes:

| Size (pixels) | Usage | File naming |
|--------------|-------|-------------|
| 16x16 | Menu bar, small lists | `icon_16x16.png` |
| 16x16@2x (32x32) | Retina menu bar | `icon_16x16@2x.png` |
| 32x32 | Lists, toolbars | `icon_32x32.png` |
| 32x32@2x (64x64) | Retina lists | `icon_32x32@2x.png` |
| 128x128 | Sidebar | `icon_128x128.png` |
| 128x128@2x (256x256) | Retina sidebar | `icon_128x128@2x.png` |
| 256x256 | Finder icon view | `icon_256x256.png` |
| 256x256@2x (512x512) | Retina Finder | `icon_256x256@2x.png` |
| 512x512 | Preview, About window | `icon_512x512.png` |
| 512x512@2x (1024x1024) | Retina preview | `icon_512x512@2x.png` |

**Critical:** The 1024x1024 version is required for App Store submission.

## Design Guidelines

### macOS Icon Style

Follow Apple's [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/app-icons) for macOS icons:

1. **Shape:** Use the rounded square template (not a literal square)
2. **Perspective:** Subtle front-facing perspective with slight depth
3. **Color:** Vibrant colors that work on light and dark backgrounds
4. **Shadow:** Soft shadow around the edges (part of the template)
5. **Simplicity:** Clear, recognizable design at all sizes
6. **No text:** Avoid text in the icon (use symbols/imagery)

### Design Recommendations for StemSeparator

Consider these themes for the icon:
- **Waveform:** Audio waveform splitting into stems
- **Layers:** Stacked layers representing vocal/instrumental/drums/bass
- **Speaker:** Speaker or headphones with separation indicator
- **Music:** Musical notes separating or branching
- **AI/Tech:** Modern, tech-focused design with audio elements

**Colors to consider:**
- **Primary:** macOS blue (#007AFF) for consistency with UI
- **Accent:** Complementary colors (purple, teal, or gradient)
- **Contrast:** Ensure visibility on both light and dark dock backgrounds

## Creating the Icon

### Option 1: Professional Design Tool

Use **Sketch**, **Figma**, or **Adobe Illustrator**:

1. Start with a 1024x1024 canvas
2. Use the [macOS App Icon Template](https://developer.apple.com/design/resources/)
3. Design your icon within the safe area
4. Export all required sizes

### Option 2: Automated Export

If you have a master 1024x1024 PNG:

```bash
# Install imagemagick
brew install imagemagick

# Create all sizes
mkdir icon.iconset
sips -z 16 16     master_icon_1024.png --out icon.iconset/icon_16x16.png
sips -z 32 32     master_icon_1024.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     master_icon_1024.png --out icon.iconset/icon_32x32.png
sips -z 64 64     master_icon_1024.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   master_icon_1024.png --out icon.iconset/icon_128x128.png
sips -z 256 256   master_icon_1024.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   master_icon_1024.png --out icon.iconset/icon_256x256.png
sips -z 512 512   master_icon_1024.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   master_icon_1024.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 master_icon_1024.png --out icon.iconset/icon_512x512@2x.png

# Generate .icns file
iconutil -c icns icon.iconset
```

This will create `icon.icns` in the current directory.

### Option 3: Online Tools

Use online icon generators:
- [AppIconBuilder](https://appiconbuilder.com/)
- [IconKitchen](https://icon.kitchen/)
- [MakeAppIcon](https://makeappicon.com/)

Upload your 1024x1024 design and download the complete `.icns` file.

## Integration Steps

### 1. Place the Icon File

```bash
# Copy your icon.icns to the resources directory
cp icon.icns packaging/macos/Resources/app_icon.icns
```

### 2. Update PyInstaller Spec

The spec file should already reference the icon:

```python
# In packaging/macos/StemSeparator_mac.spec
app = BUNDLE(
    exe,
    name='Stem Separator.app',
    icon='packaging/macos/Resources/app_icon.icns',  # ← Icon reference
    bundle_identifier='com.fratello.stemseparator',
    info_plist={
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleIconFile': 'app_icon.icns',  # ← Icon file name
        # ...
    }
)
```

### 3. Build the App

```bash
cd packaging/macos
./build_mac.sh
```

The icon will be embedded in the `.app` bundle.

## Verifying the Icon

### Check Icon in Finder

1. Build the app
2. Navigate to `packaging/macos/dist/Stem Separator.app`
3. Icon should appear in Finder
4. Open "Get Info" (Cmd+I) to see all sizes

### Check Icon in Dock

1. Run the app
2. Icon should appear in the Dock
3. Right-click → Options → "Keep in Dock"
4. Icon should look crisp on Retina displays

## Troubleshooting

### Icon Doesn't Appear

1. **Clear icon cache:**
   ```bash
   sudo rm -rf /Library/Caches/com.apple.iconservices.store
   sudo find /private/var/folders/ -name com.apple.iconservices -exec rm -rf {} \;
   killall Dock
   killall Finder
   ```

2. **Verify .icns file:**
   ```bash
   # List all images in .icns file
   sips -g all packaging/macos/Resources/app_icon.icns
   ```

3. **Check Info.plist:**
   ```bash
   plutil -p "packaging/macos/dist/Stem Separator.app/Contents/Info.plist" | grep Icon
   ```

### Icon Looks Blurry

- **Problem:** Missing @2x (Retina) sizes
- **Solution:** Ensure all @2x sizes are included in .icns file
- **Verify:** Use `iconutil -l icon.icns` to list included sizes

### Wrong Icon Appears

- **Problem:** macOS is caching old icon
- **Solution:** Clear cache (see above) and rebuild
- **Alternative:** Change `CFBundleVersion` in Info.plist

## Current Icon Status

**Status:** 🚧 No custom icon yet (using default Python/Qt icon)

**To Do:**
1. Design 1024x1024 master icon following guidelines above
2. Generate all required sizes
3. Create `app_icon.icns` file
4. Place in `packaging/macos/Resources/`
5. Rebuild app bundle

## Design Brief

For StemSeparator, consider an icon that:
- Conveys **audio processing** and **separation**
- Uses **macOS blue** (#007AFF) as primary color
- Works well at **16x16** (smallest size)
- Looks modern and professional
- Stands out among other audio apps

### Icon Inspiration

Look at these well-designed audio app icons for inspiration:
- **Logic Pro:** Modern, gradient sphere with waveform
- **GarageBand:** Minimalist guitar icon
- **Audacity:** Waveform-based design
- **iZotope RX:** Abstract audio repair symbol

## Resources

- [Apple HIG: App Icons](https://developer.apple.com/design/human-interface-guidelines/app-icons)
- [macOS App Icon Template (Sketch)](https://developer.apple.com/design/resources/)
- [IconJar](https://geticonjar.com/) - Icon management tool
- [SF Symbols](https://developer.apple.com/sf-symbols/) - System icon references

## Notes

- **File size:** A complete .icns file is typically 200-500 KB
- **Format:** Use PNG with alpha channel for transparency
- **Color space:** sRGB color profile recommended
- **Optimization:** Compress final .icns with `imageoptim` or similar

---

**Last Updated:** 2025-11-24
**Contact:** For icon design questions, consult the project maintainer or a macOS design specialist.
