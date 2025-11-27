#!/bin/bash
# Build script for ScreenCapture Audio Recorder

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "=========================================="
echo "Building ScreenCapture Audio Recorder"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "Package.swift" ]; then
    echo -e "${RED}Error: Must run from screencapture_tool directory${NC}"
    echo "Usage: ./build.sh"
    exit 1
fi

# Check if swift is installed
if ! command -v swift &> /dev/null; then
    echo -e "${RED}Error: Swift not found${NC}"
    echo "Install Xcode Command Line Tools with:"
    echo "  xcode-select --install"
    exit 1
fi

# Show Swift version
echo -e "${BLUE}Swift version:${NC}"
swift --version
echo ""

# Clean previous build (optional)
if [ "$1" == "clean" ]; then
    echo -e "${BLUE}Cleaning previous build...${NC}"
    rm -rf .build
    echo -e "${GREEN}✓ Clean complete${NC}"
    echo ""
fi

# Build in release mode
echo -e "${BLUE}Building in release mode...${NC}"
swift build -c release

# Check if build succeeded
if [ ! -f ".build/release/screencapture-recorder" ]; then
    echo ""
    echo -e "${RED}Build failed: Executable not created${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Build successful!${NC}"
echo ""

# Show binary info
BINARY_PATH=".build/release/screencapture-recorder"
BINARY_SIZE=$(du -h "$BINARY_PATH" | cut -f1)
echo -e "${BLUE}Binary: $BINARY_PATH${NC}"
echo -e "${BLUE}Size: $BINARY_SIZE${NC}"
echo ""

# Show usage
echo "Test the binary:"
echo "  $BINARY_PATH test"
echo ""
echo "List devices:"
echo "  $BINARY_PATH list-devices"
echo ""
echo "Record 5 seconds:"
echo "  $BINARY_PATH record --output test.wav --duration 5"
echo ""
