#!/bin/bash
# Build script for StemSeparator - Intel (x86_64) architecture

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "=========================================="
echo "StemSeparator Build Script (Intel x86_64)"
echo "=========================================="
echo ""

# Check architecture
ARCH=$(uname -m)
if [ "$ARCH" != "x86_64" ]; then
    echo -e "${YELLOW}Warning: You are on $ARCH architecture, but building for x86_64${NC}"
    echo -e "${YELLOW}This is cross-compilation and may not work correctly.${NC}"
    echo ""
fi

# Check if we're in the project root
if [ ! -f "main.py" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    echo "Usage: ./packaging/build_intel.sh"
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
MODEL_COUNT=$(find resources/models -name "*.ckpt" -o -name "*.yaml" | wc -l | xargs)
if [ "$MODEL_COUNT" -lt 3 ]; then
    echo -e "${YELLOW}Warning: Models may not be fully downloaded (found $MODEL_COUNT files)${NC}"
    echo -e "${YELLOW}Run: python packaging/download_models.py${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓ Found $MODEL_COUNT model files${NC}"
fi

# Clean previous builds
echo ""
echo -e "${BLUE}Cleaning previous builds...${NC}"
rm -rf build/ dist/StemSeparator-intel.app dist/StemSeparator-intel.dmg
echo -e "${GREEN}✓ Clean complete${NC}"

# Run PyInstaller
echo ""
echo -e "${BLUE}Running PyInstaller (this may take 5-10 minutes)...${NC}"
echo -e "${BLUE}Spec file: packaging/StemSeparator-intel.spec${NC}"
echo ""

pyinstaller --clean packaging/StemSeparator-intel.spec

# Check if build succeeded
if [ ! -d "dist/StemSeparator-intel.app" ]; then
    echo ""
    echo -e "${RED}Build failed: Application bundle not created${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Application bundle created successfully${NC}"

# Show bundle size
APP_SIZE=$(du -sh dist/StemSeparator-intel.app | cut -f1)
echo -e "${BLUE}Application size: $APP_SIZE${NC}"

# Create DMG installer
echo ""
echo -e "${BLUE}Creating DMG installer...${NC}"

# Simple DMG creation (no custom background for now)
DMG_NAME="StemSeparator-intel.dmg"
DMG_PATH="dist/$DMG_NAME"

# Remove existing DMG if present
rm -f "$DMG_PATH"

# Create temporary directory for DMG contents
DMG_TEMP="build/dmg_temp"
mkdir -p "$DMG_TEMP"

# Copy app to temp directory
cp -R dist/StemSeparator-intel.app "$DMG_TEMP/"

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
echo "  Application: dist/StemSeparator-intel.app ($APP_SIZE)"
if [ -f "$DMG_PATH" ]; then
    echo "  Installer:   $DMG_PATH ($DMG_SIZE)"
fi
echo ""
echo "Next steps:"
echo "  1. Test the application:"
echo "     open dist/StemSeparator-intel.app"
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
