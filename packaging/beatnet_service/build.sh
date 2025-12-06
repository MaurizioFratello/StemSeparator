#!/bin/bash
#
# Build BeatNet Beat-Service Binary
#
# Requirements:
#   - Conda environment 'beatnet-env' with Python 3.9
#   - All dependencies from requirements.txt installed
#
# Usage:
#   ./build.sh              # Build for current architecture
#   ./build.sh --clean      # Clean build artifacts first
#
# Output:
#   dist/beatnet-service    # Standalone binary

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
ENV_NAME="${BEATNET_ENV:-beatnet-env}"
OUTPUT_NAME="beatnet-service"

echo "=== BeatNet Beat-Service Build ==="
echo "Script directory: $SCRIPT_DIR"
echo "Environment: $ENV_NAME"

# Check for --clean flag
if [[ "$1" == "--clean" ]]; then
    echo "Cleaning build artifacts..."
    rm -rf build/ dist/ *.spec 2>/dev/null || true
    echo "Clean complete."
fi

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "ERROR: conda not found. Please install Miniconda or Anaconda."
    exit 1
fi

# Activate conda environment
echo "Activating conda environment: $ENV_NAME"
eval "$(conda shell.bash hook)"
conda activate "$ENV_NAME" 2>/dev/null || {
    echo "ERROR: Environment '$ENV_NAME' not found."
    echo "Create it with: conda create -n $ENV_NAME python=3.9"
    echo "Then install: pip install -r requirements.txt"
    exit 1
}

# Verify Python version
PYTHON_VERSION=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Python version: $PYTHON_VERSION"

if [[ "$PYTHON_VERSION" != "3.8" && "$PYTHON_VERSION" != "3.9" ]]; then
    echo "WARNING: Python $PYTHON_VERSION detected. BeatNet works best with 3.8 or 3.9."
fi

# Verify BeatNet is installed, auto-install if missing
echo "Checking for BeatNet..."
if ! python -c "from BeatNet.BeatNet import BeatNet" 2>&1; then
    echo "BeatNet not found. Installing dependencies automatically..."
    echo ""

    # Install numba via conda (required for Apple Silicon compatibility)
    echo "Installing numba via conda..."
    conda install -y -c conda-forge numba=0.54.1

    # Install cython and madmom with special build flags
    echo "Installing madmom..."
    pip install cython
    pip install --no-build-isolation madmom

    # Install remaining dependencies
    echo "Installing BeatNet and other dependencies..."
    pip install pyaudio BeatNet soundfile torch pyinstaller

    # Verify installation
    echo "Verifying BeatNet installation..."
    if ! python -c "from BeatNet.BeatNet import BeatNet"; then
        echo "ERROR: Failed to install BeatNet dependencies."
        echo "BeatNet import test failed. Check the error above."
        exit 1
    fi

    echo "✓ Dependencies installed successfully"
    echo ""
fi

echo "Building binary with PyInstaller..."

# Build with PyInstaller
pyinstaller \
    --onefile \
    --name "$OUTPUT_NAME" \
    --distpath dist \
    --workpath build \
    --specpath . \
    --hidden-import BeatNet \
    --hidden-import BeatNet.BeatNet \
    --hidden-import madmom \
    --hidden-import madmom.features \
    --hidden-import madmom.features.beats \
    --hidden-import madmom.features.downbeats \
    --hidden-import madmom.ml \
    --hidden-import madmom.ml.nn \
    --hidden-import numba \
    --hidden-import torch \
    --hidden-import soundfile \
    --hidden-import numpy \
    --collect-data BeatNet \
    --collect-data madmom \
    --noconfirm \
    src/__main__.py

# Verify output
if [[ -f "dist/$OUTPUT_NAME" ]]; then
    echo ""
    echo "=== Build Successful ==="
    echo "Binary: $SCRIPT_DIR/dist/$OUTPUT_NAME"
    echo "Size: $(du -h "dist/$OUTPUT_NAME" | cut -f1)"
    echo ""
    echo "Test with:"
    echo "  ./dist/$OUTPUT_NAME --input /path/to/audio.wav --verbose"
else
    echo "ERROR: Build failed - binary not found"
    exit 1
fi

