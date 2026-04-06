#!/usr/bin/env bash
set -euo pipefail

echo "=== Building StemSeparator (Windows onedir) ==="
echo "This script must be run on Windows (or under compatible tooling)."

if [[ "${OS:-}" != "Windows_NT" && "$(uname -s 2>/dev/null || true)" != MINGW* && "$(uname -s 2>/dev/null || true)" != MSYS* ]]; then
  echo "Warning: Non-Windows environment detected."
  echo "The generated artifact is intended for Windows and should be built/tested on Windows."
fi

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt

if [[ ! -f "packaging/StemSeparator-windows.spec" ]]; then
  echo "Error: packaging/StemSeparator-windows.spec not found"
  exit 1
fi

rm -rf build dist
pyinstaller --clean --noconfirm packaging/StemSeparator-windows.spec

echo "Build complete. Output directory:"
echo "  dist/StemSeparator/"
