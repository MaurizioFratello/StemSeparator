#!/bin/bash
# Build script for StemSeparator - Both architectures

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "=========================================="
echo "StemSeparator Build Script (All Architectures)"
echo "=========================================="
echo ""

# Check if we're in the project root
if [ ! -f "main.py" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    echo "Usage: ./packaging/build_all.sh"
    exit 1
fi

# Detect current architecture
ARCH=$(uname -m)
echo -e "${BLUE}Current architecture: $ARCH${NC}"
echo ""

# Build Intel version
echo -e "${BLUE}Building Intel (x86_64) version...${NC}"
echo ""
./packaging/build_intel.sh

echo ""
echo "=========================================="
echo ""

# Build Apple Silicon version
echo -e "${BLUE}Building Apple Silicon (arm64) version...${NC}"
echo ""
./packaging/build_arm64.sh

echo ""
echo "=========================================="
echo -e "${GREEN}All Builds Complete!${NC}"
echo "=========================================="
echo ""
echo "Output files:"
echo ""

if [ -d "dist/StemSeparator-intel.app" ]; then
    INTEL_SIZE=$(du -sh dist/StemSeparator-intel.app | cut -f1)
    echo "Intel (x86_64):"
    echo "  Application: dist/StemSeparator-intel.app ($INTEL_SIZE)"
    if [ -f "dist/StemSeparator-intel.dmg" ]; then
        INTEL_DMG_SIZE=$(du -sh dist/StemSeparator-intel.dmg | cut -f1)
        echo "  Installer:   dist/StemSeparator-intel.dmg ($INTEL_DMG_SIZE)"
    fi
    echo ""
fi

if [ -d "dist/StemSeparator-arm64.app" ]; then
    ARM_SIZE=$(du -sh dist/StemSeparator-arm64.app | cut -f1)
    echo "Apple Silicon (arm64):"
    echo "  Application: dist/StemSeparator-arm64.app ($ARM_SIZE)"
    if [ -f "dist/StemSeparator-arm64.dmg" ]; then
        ARM_DMG_SIZE=$(du -sh dist/StemSeparator-arm64.dmg | cut -f1)
        echo "  Installer:   dist/StemSeparator-arm64.dmg ($ARM_DMG_SIZE)"
    fi
    echo ""
fi

echo "Distribution:"
echo "  - Intel Macs: Use StemSeparator-intel.dmg"
echo "  - Apple Silicon Macs (M1/M2/M3): Use StemSeparator-arm64.dmg"
echo ""
