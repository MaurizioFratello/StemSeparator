#!/bin/bash
# Build script for StemSeparator - Apple Silicon (arm64) architecture

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "=========================================="
echo "StemSeparator Build Script (Apple Silicon arm64)"
echo "=========================================="
echo ""

# Check architecture
ARCH=$(uname -m)
if [ "$ARCH" != "arm64" ]; then
    echo -e "${YELLOW}Warning: You are on $ARCH architecture, but building for arm64${NC}"
    echo -e "${YELLOW}This is cross-compilation and may not work correctly.${NC}"
    echo ""
fi

# Check if we're in the project root
if [ ! -f "main.py" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    echo "Usage: ./packaging/build_arm64.sh"
    exit 1
fi

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo -e "${RED}Error: PyInstaller not found${NC}"
    echo "Install with: pip install -r requirements-build.txt"
    exit 1
fi

# Check if models are downloaded
echo -e "${BLUE}Checking for AI models...${NC}"
MODEL_COUNT=$(find resources/models -type f \( -name "*.ckpt" -o -name "*.yaml" \) 2>/dev/null | wc -l | xargs)
if [ "$MODEL_COUNT" -eq 0 ]; then
    echo -e "${RED}ERROR: No models found in resources/models/${NC}"
    echo -e "${YELLOW}You must download models before building!${NC}"
    echo -e "${YELLOW}Run: python packaging/download_models.py${NC}"
    echo ""
    exit 1
elif [ "$MODEL_COUNT" -lt 6 ]; then
    echo -e "${YELLOW}Warning: Only found $MODEL_COUNT model files (expected ~10 for all 4 models)${NC}"
    echo -e "${YELLOW}Some models may be missing. Run: python packaging/download_models.py${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓ Found $MODEL_COUNT model files${NC}"
fi

# Build Swift ScreenCapture tool
echo ""
echo -e "${BLUE}Building Swift ScreenCapture tool...${NC}"
SCREENCAPTURE_DIR="packaging/screencapture_tool"
if [ ! -d "$SCREENCAPTURE_DIR" ]; then
    echo -e "${YELLOW}Warning: ScreenCapture tool directory not found${NC}"
    echo -e "${YELLOW}ScreenCaptureKit recording will not be available${NC}"
else
    cd "$SCREENCAPTURE_DIR"
    if [ -f "build.sh" ]; then
        # Build with explicit architecture for arm64
        # WHY: Ensure we build the correct architecture binary for Apple Silicon
        if ./build.sh > /dev/null 2>&1; then
            # Verify binary exists in expected location
            BINARY_PATH=".build/arm64-apple-macosx/release/screencapture-recorder"
            if [ ! -f "$BINARY_PATH" ]; then
                # Fallback to generic release path
                BINARY_PATH=".build/release/screencapture-recorder"
            fi
            
            if [ -f "$BINARY_PATH" ]; then
                # Ensure binary is executable
                chmod +x "$BINARY_PATH" 2>/dev/null || true
                
                # Verify it's actually executable
                if [ -x "$BINARY_PATH" ]; then
                    BINARY_SIZE=$(du -h "$BINARY_PATH" | cut -f1)
                    echo -e "${GREEN}✓ ScreenCapture tool built successfully${NC}"
                    echo -e "${BLUE}  Binary: $BINARY_PATH ($BINARY_SIZE)${NC}"
                else
                    echo -e "${YELLOW}Warning: Binary exists but is not executable${NC}"
                    echo -e "${YELLOW}ScreenCaptureKit recording may not work${NC}"
                fi
            else
                echo -e "${YELLOW}Warning: ScreenCapture tool build completed but binary not found${NC}"
                echo -e "${YELLOW}ScreenCaptureKit recording will not be available${NC}"
            fi
        else
            echo -e "${YELLOW}Warning: ScreenCapture tool build failed${NC}"
            echo -e "${YELLOW}ScreenCaptureKit recording will not be available${NC}"
        fi
    else
        echo -e "${YELLOW}Warning: build.sh not found in screencapture_tool${NC}"
    fi
    cd - > /dev/null
fi

# Clean previous builds
echo ""
echo -e "${BLUE}Cleaning previous builds...${NC}"

# Ensure StemSeparator is not running
if pgrep -f "StemSeparator" > /dev/null; then
    echo -e "${YELLOW}StemSeparator is running. Attempting to close it...${NC}"
    pkill -f "StemSeparator" || true
    sleep 2
fi

# Force remove directory if it exists
if [ -d "dist/StemSeparator" ]; then
    echo -e "${YELLOW}Removing dist/StemSeparator...${NC}"
    rm -rf "dist/StemSeparator" || echo -e "${RED}Failed to remove dist/StemSeparator. Check permissions or if file is in use.${NC}"
fi

rm -rf build/ dist/StemSeparator-arm64.app dist/StemSeparator-arm64.dmg dist/StemSeparator
echo -e "${GREEN}✓ Clean complete${NC}"

# Ensure build directory structure exists for PyInstaller
# WHY: PyInstaller requires this directory to exist and be writable before it runs
BUILD_DIR="build/StemSeparator-arm64"
mkdir -p "$BUILD_DIR"
mkdir -p dist

# Verify build directory is writable
if [ ! -w "$BUILD_DIR" ]; then
    echo -e "${RED}Error: Build directory is not writable: $BUILD_DIR${NC}"
    exit 1
fi

# Test write access
if ! touch "$BUILD_DIR/.write_test" 2>/dev/null; then
    echo -e "${RED}Error: Cannot write to build directory: $BUILD_DIR${NC}"
    exit 1
fi
rm -f "$BUILD_DIR/.write_test"

echo -e "${GREEN}✓ Build directory ready: $BUILD_DIR${NC}"

# Run PyInstaller
echo ""
echo -e "${BLUE}Running PyInstaller (this may take 5-10 minutes)...${NC}"
echo -e "${BLUE}Spec file: packaging/StemSeparator-arm64.spec${NC}"
echo ""

# Set environment to avoid OpenMP duplicate library error during PyTorch analysis
export KMP_DUPLICATE_LIB_OK=TRUE
export OMP_NUM_THREADS=1

# Note: We don't use --clean here because we already cleaned manually above
# and --clean might interfere with directory creation
# Use --noconfirm to avoid interactive prompts when PyInstaller needs to remove directories
pyinstaller --noconfirm packaging/StemSeparator-arm64.spec

# Check if build succeeded
if [ ! -d "dist/StemSeparator-arm64.app" ]; then
    echo ""
    echo -e "${RED}Build failed: Application bundle not created${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Application bundle created successfully${NC}"

# Show bundle size
APP_SIZE=$(du -sh dist/StemSeparator-arm64.app | cut -f1)
echo -e "${BLUE}Application size: $APP_SIZE${NC}"

# Create DMG installer
echo ""
echo -e "${BLUE}Creating DMG installer...${NC}"

# Simple DMG creation (no custom background for now)
DMG_NAME="StemSeparator-arm64.dmg"
DMG_PATH="dist/$DMG_NAME"

# Remove existing DMG if present
rm -f "$DMG_PATH"

# Create temporary directory for DMG contents
DMG_TEMP="build/dmg_temp"
mkdir -p "$DMG_TEMP"

# Copy app to temp directory
cp -R dist/StemSeparator-arm64.app "$DMG_TEMP/"

# Create Applications symlink
ln -s /Applications "$DMG_TEMP/Applications"

# Create DMG
hdiutil create -volname "Stem Separator" \
    -srcfolder "$DMG_TEMP" \
    -ov -format UDZO \
    "$DMG_PATH"

# Clean up temp directory
rm -rf "$DMG_TEMP"

if [ -f "$DMG_PATH" ]; then
    DMG_SIZE=$(du -sh "$DMG_PATH" | cut -f1)
    echo -e "${GREEN}✓ DMG created: $DMG_PATH ($DMG_SIZE)${NC}"
else
    echo -e "${YELLOW}Warning: DMG creation failed, but app bundle is available${NC}"
fi

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}Build Complete!${NC}"
echo "=========================================="
echo ""
echo "Output files:"
echo "  Application: dist/StemSeparator-arm64.app ($APP_SIZE)"
if [ -f "$DMG_PATH" ]; then
    echo "  Installer:   $DMG_PATH ($DMG_SIZE)"
fi
echo ""
echo "Next steps:"
echo "  1. Test the application:"
echo "     open dist/StemSeparator-arm64.app"
echo ""
if [ -f "$DMG_PATH" ]; then
    echo "  2. Test the installer:"
    echo "     open $DMG_PATH"
    echo ""
fi
echo "  3. Distribute the DMG file to users"
echo ""
echo -e "${YELLOW}Note: App is unsigned. Users will need to right-click and 'Open'${NC}"
echo "      the first time to bypass Gatekeeper."
echo ""
