# Application Icon

## Required Format

macOS applications require an `.icns` file (Apple Icon Image format).

## Creating the Icon

1. **Create a 1024x1024 PNG** with your app logo/icon
2. **Convert to .icns** using one of these methods:

### Method 1: Using iconutil (macOS built-in)
```bash
# Create iconset directory
mkdir icon.iconset

# Create required sizes (copy/resize your 1024x1024 source):
sips -z 16 16     icon-1024.png --out icon.iconset/icon_16x16.png
sips -z 32 32     icon-1024.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     icon-1024.png --out icon.iconset/icon_32x32.png
sips -z 64 64     icon-1024.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   icon-1024.png --out icon.iconset/icon_128x128.png
sips -z 256 256   icon-1024.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   icon-1024.png --out icon.iconset/icon_256x256.png
sips -z 512 512   icon-1024.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   icon-1024.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 icon-1024.png --out icon.iconset/icon_512x512@2x.png

# Convert to .icns
iconutil -c icns icon.iconset -o packaging/icon.icns
```

### Method 2: Using Image2Icon (App)
1. Download Image2Icon from Mac App Store (free)
2. Drag your 1024x1024 PNG into the app
3. Export as .icns
4. Save to `packaging/icon.icns`

### Method 3: Using online converter
1. Visit https://cloudconvert.com/png-to-icns
2. Upload your 1024x1024 PNG
3. Download the .icns file
4. Save to `packaging/icon.icns`

## Placeholder Icon

For testing, PyInstaller will use the default Python icon if `icon.icns` is not present.

## Icon Design Suggestions

For StemSeparator, consider:
- Waveform visualization
- Musical note with separation arrows
- Stem/plant metaphor (separating into branches)
- Audio spectrum with distinct colors
- Colors: Purple/blue to match app theme
