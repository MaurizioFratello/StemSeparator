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

# Build BeatNet Beat-Service binary (AUTOMATIC SETUP)
echo ""
echo -e "${BLUE}Building BeatNet Beat-Service binary...${NC}"
BEATNET_DIR="packaging/beatnet_service"

if [ ! -d "$BEATNET_DIR" ]; then
    echo -e "${RED}ERROR: BeatNet service directory not found${NC}"
    echo -e "${RED}BeatNet is required for the application!${NC}"
    exit 1
fi

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo -e "${RED}ERROR: conda not found. Please install Miniconda or Anaconda.${NC}"
    echo -e "${BLUE}Download from: https://docs.conda.io/en/latest/miniconda.html${NC}"
    exit 1
fi

cd "$BEATNET_DIR"

# Setup conda for bash
eval "$(conda shell.bash hook)"

# Check if beatnet-env exists, create if not
ENV_NAME="beatnet-env"
if ! conda env list | grep -q "^${ENV_NAME} "; then
    echo -e "${YELLOW}BeatNet environment not found. Creating automatically...${NC}"
    # IMPORTANT: Python 3.8 required for numba 0.54.1 compatibility
    conda create -n "$ENV_NAME" python=3.8 -y
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: Failed to create beatnet-env${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Created beatnet-env (Python 3.8)${NC}"
fi

# Note: We don't install dependencies here - build.sh will handle that
# with the correct installation order (conda install numba, then pip packages)

# Build binary
echo -e "${BLUE}Building BeatNet binary...${NC}"
if ! [ -f "build.sh" ]; then
    echo -e "${RED}ERROR: build.sh not found in beatnet_service${NC}"
    exit 1
fi

# Build with output visible for debugging
./build.sh
BUILD_STATUS=$?

if [ $BUILD_STATUS -eq 0 ]; then
    BEATNET_BINARY="dist/beatnet-service"
    if [ -f "$BEATNET_BINARY" ]; then
        chmod +x "$BEATNET_BINARY" 2>/dev/null || true
        if [ -x "$BEATNET_BINARY" ]; then
            BEATNET_SIZE=$(du -h "$BEATNET_BINARY" | cut -f1)
            echo -e "${GREEN}✓ BeatNet service built successfully${NC}"
            echo -e "${BLUE}  Binary: $BEATNET_BINARY ($BEATNET_SIZE)${NC}"
        else
            echo -e "${RED}ERROR: BeatNet binary exists but is not executable${NC}"
            exit 1
        fi
    else
        echo -e "${RED}ERROR: BeatNet service build completed but binary not found${NC}"
        exit 1
    fi
else
    echo -e "${RED}ERROR: BeatNet service build failed${NC}"
    exit 1
fi

# Deactivate beatnet-env and return to original environment
conda deactivate
cd - > /dev/null

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

# Resolve PyInstaller command (prefer current env's python -m PyInstaller, then CLI)
if command -v python >/dev/null 2>&1 && python -m PyInstaller --version >/dev/null 2>&1; then
    echo -e "${BLUE}Using python -m PyInstaller from current environment${NC}"
    PYINSTALLER_CMD=("python" "-m" "PyInstaller")
elif command -v python3 >/dev/null 2>&1 && python3 -m PyInstaller --version >/dev/null 2>&1; then
    echo -e "${BLUE}Using python3 -m PyInstaller from current environment${NC}"
    PYINSTALLER_CMD=("python3" "-m" "PyInstaller")
else
    PYINSTALLER_BIN=$(command -v pyinstaller || true)
    if [ -n "$PYINSTALLER_BIN" ]; then
        echo -e "${BLUE}Using PyInstaller executable: $PYINSTALLER_BIN${NC}"
        PYINSTALLER_CMD=("$PYINSTALLER_BIN")
    else
        echo -e "${RED}Error: PyInstaller not found in current environment. Activate the build env (e.g., conda activate stem-separator) and ensure PyInstaller is installed.${NC}"
        exit 1
    fi
fi

# Note: We don't use --clean here because we already cleaned manually above
# and --clean might interfere with directory creation
# Use --noconfirm to avoid interactive prompts when PyInstaller needs to remove directories
"${PYINSTALLER_CMD[@]}" --noconfirm packaging/StemSeparator-arm64.spec

# Check if build succeeded
if [ ! -d "dist/StemSeparator-arm64.app" ]; then
    echo ""
    echo -e "${RED}Build failed: Application bundle not created${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Application bundle created successfully${NC}"

# Remove duplicate FFmpeg dylibs from Frameworks/ (PyInstaller auto-bundles them)
# WHY: Keep only the copies in Resources/bin/ to avoid conflicts with PySide6
echo ""
echo -e "${BLUE}Removing duplicate FFmpeg libraries from Frameworks/...${NC}"
FRAMEWORKS_DIR="dist/StemSeparator-arm64.app/Contents/Frameworks"
if [ -d "$FRAMEWORKS_DIR" ]; then
    # Remove FFmpeg dylibs (but NOT PySide6's FFmpeg libraries)
    for dylib in libavcodec.61.dylib libavfilter.10.dylib libavformat.61.dylib \
                 libavutil.59.dylib libavdevice.61.dylib libpostproc.58.dylib \
                 libswresample.5.dylib libswscale.8.dylib; do
        if [ -f "$FRAMEWORKS_DIR/$dylib" ]; then
            rm -f "$FRAMEWORKS_DIR/$dylib"
            echo "  Removed: $dylib"
        fi
    done
    # Also remove FFmpeg's dependency dylibs to save space and avoid conflicts
    for dylib in libaom*.dylib libass*.dylib libdav1d*.dylib libmp3lame*.dylib \
                 libopus*.dylib librav1e*.dylib libvorbis*.dylib libvpx*.dylib \
                 libwebp*.dylib libx264*.dylib libx265*.dylib; do
        if [ -f "$FRAMEWORKS_DIR/$dylib" ]; then
            rm -f "$FRAMEWORKS_DIR/$dylib"
        fi
    done
    echo -e "${GREEN}✓ Duplicate FFmpeg libraries removed${NC}"
else
    echo -e "${YELLOW}Warning: Frameworks directory not found${NC}"
fi

# Fix FFmpeg library paths if bundled
echo ""
echo -e "${BLUE}Fixing FFmpeg library paths...${NC}"
if [ -f "packaging/fix_ffmpeg_libs.sh" ]; then
    ./packaging/fix_ffmpeg_libs.sh "dist/StemSeparator-arm64.app"
else
    echo -e "${YELLOW}Warning: fix_ffmpeg_libs.sh not found${NC}"
fi

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
