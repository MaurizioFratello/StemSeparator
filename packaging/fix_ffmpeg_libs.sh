#!/bin/bash
# Post-build script to fix FFmpeg library paths
# This ensures FFmpeg uses its own dylibs from Resources/bin/, not PySide6's libraries

set -e

APP_PATH="$1"
BIN_DIR="$APP_PATH/Contents/Resources/bin"
FFMPEG_BIN="$BIN_DIR/ffmpeg"

if [ ! -f "$FFMPEG_BIN" ]; then
    echo "FFmpeg not found in bundle, skipping library fixes"
    exit 0
fi

echo "Fixing FFmpeg library paths..."

# Remove quarantine flag if present (macOS Gatekeeper)
xattr -dr com.apple.quarantine "$BIN_DIR" 2>/dev/null || true

# Make ffmpeg writable temporarily
chmod +w "$FFMPEG_BIN"

# Fix rpath to look in same directory first
install_name_tool -add_rpath "@executable_path" "$FFMPEG_BIN" 2>/dev/null || true
install_name_tool -add_rpath "@loader_path" "$FFMPEG_BIN" 2>/dev/null || true

# Fix all dylib references to use @rpath
for dylib in "$BIN_DIR"/*.dylib; do
    if [ -f "$dylib" ]; then
        dylib_name=$(basename "$dylib")

        # Make dylib writable
        chmod +w "$dylib"

        # Update ffmpeg to use @rpath for this dylib
        install_name_tool -change "/opt/homebrew/opt/"*"/$dylib_name" "@rpath/$dylib_name" "$FFMPEG_BIN" 2>/dev/null || true
        install_name_tool -change "/opt/homebrew/lib/$dylib_name" "@rpath/$dylib_name" "$FFMPEG_BIN" 2>/dev/null || true
        install_name_tool -change "/usr/local/lib/$dylib_name" "@rpath/$dylib_name" "$FFMPEG_BIN" 2>/dev/null || true

        # Fix the dylib's own ID
        install_name_tool -id "@rpath/$dylib_name" "$dylib" 2>/dev/null || true

        # Add rpath to the dylib itself
        install_name_tool -add_rpath "@loader_path" "$dylib" 2>/dev/null || true

        # Fix inter-dylib references
        for other_dylib in "$BIN_DIR"/*.dylib; do
            if [ -f "$other_dylib" ] && [ "$dylib" != "$other_dylib" ]; then
                other_name=$(basename "$other_dylib")
                install_name_tool -change "/opt/homebrew/opt/"*"/$other_name" "@rpath/$other_name" "$dylib" 2>/dev/null || true
                install_name_tool -change "/opt/homebrew/lib/$other_name" "@rpath/$other_name" "$dylib" 2>/dev/null || true
                install_name_tool -change "/usr/local/lib/$other_name" "@rpath/$other_name" "$dylib" 2>/dev/null || true
            fi
        done

        echo "  Fixed: $dylib_name"
    fi
done

# Restore executable permissions and sign
chmod +x "$FFMPEG_BIN"
chmod +x "$BIN_DIR"/*.dylib 2>/dev/null || true

# Ad-hoc code sign to prevent Gatekeeper from killing the process
codesign --force --deep --sign - "$FFMPEG_BIN" 2>/dev/null || true
for dylib in "$BIN_DIR"/*.dylib; do
    if [ -f "$dylib" ]; then
        codesign --force --sign - "$dylib" 2>/dev/null || true
    fi
done

echo "✓ FFmpeg library paths fixed and code-signed"
