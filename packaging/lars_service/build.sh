#!/bin/bash
#
# Build LARS Service Binary
#
# Requirements:
#   - Conda environment 'lars-env' with Python 3.10
#   - All dependencies from requirements.txt installed
#
# Usage:
#   ./build.sh              # Build for current architecture
#   ./build.sh --clean      # Clean build artifacts first
#
# Output:
#   dist/lars-service       # Standalone binary

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
ENV_NAME="${LARS_ENV:-lars-env}"
OUTPUT_NAME="lars-service"
PYTHON_VERSION="3.10"

echo "=== LARS Service Build ==="
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
    echo "Creating environment with Python $PYTHON_VERSION..."
    conda create -n "$ENV_NAME" python=$PYTHON_VERSION -y
    conda activate "$ENV_NAME"
}

# Verify Python version
CURRENT_PYTHON_VERSION=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Python version: $CURRENT_PYTHON_VERSION"

if [[ "$CURRENT_PYTHON_VERSION" != "3.9" && "$CURRENT_PYTHON_VERSION" != "3.10" ]]; then
    echo "WARNING: Python $CURRENT_PYTHON_VERSION detected. LARS works best with 3.9 or 3.10."
fi

# Check and install dependencies
echo "Checking dependencies..."
MISSING_DEPS=false

# Check for required packages
for pkg in torch soundfile numpy scipy librosa pyinstaller; do
    if ! python -c "import $pkg" 2>/dev/null; then
        echo "Missing package: $pkg"
        MISSING_DEPS=true
    fi
done

if $MISSING_DEPS; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
    echo "✓ Dependencies installed successfully"
else
    echo "✓ All dependencies present"
fi

# Verify imports
echo "Verifying imports..."
python -c "
import torch
import soundfile
import numpy
import scipy
import librosa
print('✓ All imports successful')
" || {
    echo "ERROR: Import verification failed"
    exit 1
}

echo ""
echo "Building binary with PyInstaller..."

# Use spec file if available, otherwise build with command-line args
if [[ -f "lars-service.spec" ]]; then
    echo "Using lars-service.spec"
    pyinstaller \
        --noconfirm \
        --clean \
        lars-service.spec
else
    echo "Building with inline configuration"
    pyinstaller \
        --onefile \
        --name "$OUTPUT_NAME" \
        --distpath dist \
        --workpath build \
        --specpath . \
        --hidden-import torch \
        --hidden-import torchaudio \
        --hidden-import soundfile \
        --hidden-import numpy \
        --hidden-import scipy \
        --hidden-import scipy.signal \
        --hidden-import librosa \
        --noconfirm \
        --clean \
        src/__main__.py
fi

# Verify output
if [[ -f "dist/$OUTPUT_NAME" ]]; then
    echo ""
    echo "=== Build Successful ==="
    echo "Binary: $SCRIPT_DIR/dist/$OUTPUT_NAME"

    # Make executable
    chmod +x "dist/$OUTPUT_NAME"

    # Show size
    if command -v du &> /dev/null; then
        echo "Size: $(du -h "dist/$OUTPUT_NAME" | cut -f1)"
    fi

    echo ""
    echo "Test with:"
    echo "  ./dist/$OUTPUT_NAME separate --input /path/to/drums.wav --output-dir /tmp/lars_output --verbose"
    echo ""

    # Quick test
    echo "Running quick test..."
    if ./dist/$OUTPUT_NAME --help >/dev/null 2>&1; then
        echo "✓ Binary responds to --help"
    else
        echo "⚠ Warning: Binary may have issues (--help failed)"
    fi
else
    echo "ERROR: Build failed - binary not found"
    exit 1
fi
