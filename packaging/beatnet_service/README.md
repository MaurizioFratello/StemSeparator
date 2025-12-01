# BeatNet Beat-Service

Standalone CLI tool for beat and downbeat detection, designed to run as a subprocess from StemSeparator.

## Why a Separate Binary?

BeatNet requires dependencies (numba 0.54.1, madmom) that conflict with the main StemSeparator environment (Python 3.11). By building BeatNet as a separate binary:

1. **Isolation**: No dependency conflicts with main app
2. **Stability**: Process isolation prevents resource leaks
3. **Portability**: Single binary, no runtime dependencies for end users

## Requirements

- **Python 3.8** (required for numba 0.54.1 compatibility)
- Conda for isolated environment (required on Apple Silicon)

## Setup Development Environment

```bash
# Create isolated environment with Python 3.8
conda create -n beatnet-env python=3.8
conda activate beatnet-env

# Install numba stack via conda (required - pip build fails on Apple Silicon)
# Conda will automatically select compatible numpy/llvmlite versions
conda install -c conda-forge numba=0.54.1

# Install cython for madmom build
pip install cython setuptools wheel

# Install madmom WITHOUT build isolation (required for Cython access)
pip install --no-build-isolation madmom

# Install remaining dependencies via pip
pip install BeatNet soundfile torch pyinstaller
```

**Important Notes:**
- **Python 3.8 is required** - numba 0.54.1 has version constraints incompatible with 3.9+
- `numba`, `numpy`, and `llvmlite` must be installed via **conda** (not pip) on Apple Silicon
- madmom requires `--no-build-isolation` to access Cython during build

## Usage (Development)

```bash
# Activate environment
conda activate beatnet-env

# Run directly
python -m src --input /path/to/audio.wav --verbose

# Or as module
python src/__main__.py --input /path/to/audio.wav --device auto
```

## CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--input PATH` | Audio file to analyze | (required) |
| `--output PATH\|-` | Output JSON to file or stdout | `-` (stdout) |
| `--max-duration SEC` | Limit analysis duration | None (full file) |
| `--device DEVICE` | `auto`, `mps`, `cuda`, `cpu` | `auto` |
| `--verbose` | Enable stderr logging | False |

## Output Format

Success (stdout, exit 0):

```json
{
  "version": "1.0.0",
  "model": "BeatNet-1.1.3",
  "backend": "mps",
  "tempo": 123.45,
  "tempo_confidence": 0.92,
  "time_signature": "4/4",
  "beats": [
    { "time": 0.512, "index": 0, "bar": 1, "beat_in_bar": 1 }
  ],
  "downbeats": [
    { "time": 0.512, "bar": 1 }
  ],
  "analysis_duration": 12.34,
  "audio_duration": 180.0,
  "warnings": []
}
```

Error (stdout, exit 1):

```json
{
  "error": "InputError",
  "message": "Audio file not found",
  "details": { "path": "/invalid/path.wav" }
}
```

## Build Binary

```bash
# Ensure environment is active
conda activate beatnet-env

# Build with PyInstaller
./build.sh

# Output: dist/beatnet-service
```

## Integration with StemSeparator

The built binary should be copied to `resources/beatnet/beatnet-service` or bundled via the main PyInstaller spec.

StemSeparator's `beat_service_client.py` will locate and invoke this binary as a subprocess.

## Performance Targets

| Track Length | Target Analysis Time | Max Time |
|--------------|---------------------|----------|
| 3-5 min | < 10s (Apple Silicon) | 30s |

## Device Priority

When `--device auto` is specified:

1. **MPS** (Apple Silicon Metal Performance Shaders) - preferred on M1/M2/M3
2. **CUDA** (NVIDIA GPU) - if available
3. **CPU** - fallback

