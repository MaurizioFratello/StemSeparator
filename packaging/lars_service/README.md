# LARS Service

Standalone drum separation service for StemSeparator using **LarsNet** from Politecnico di Milano.

## Overview

LARS (Layered Audio Recognition System) is a dedicated service that separates drum tracks into individual components:

- **Kick** - Bass drum
- **Snare** - Snare drum
- **Toms** - Tom drums
- **Hi-Hat** - Hi-hat cymbals
- **Cymbals** - Crash and ride cymbals

## Architecture

### LarsNet Model (Primary)

LarsNet is a state-of-the-art drum separation model using **5 parallel U-Nets**:

- **Research**: Politecnico di Milano
- **Repository**: https://github.com/polimi-ispl/larsnet
- **Training Dataset**: StemGMD (1,224 hours of isolated drums)
- **Performance**: Faster than real-time
- **Quality**: Professional-grade separation with optional α-Wiener filtering

### Fallback Processors

The service automatically falls back if LarsNet is unavailable:

1. **LarsNet (5 U-Nets)** ⭐ BEST - Requires pretrained models (562 MB)
2. **Demucs + Filtering** - Frequency-based workaround using Demucs
3. **Placeholder** - Gain-based separation (testing only)

## Setup

### 1. Install Dependencies

The LARS service runs in a **separate Python 3.10 environment** (isolated from the main StemSeparator app which uses Python 3.11):

```bash
cd packaging/lars_service/
conda create -n lars-env python=3.10 -y
conda activate lars-env
pip install -r requirements.txt
```

### 2. Download LarsNet Models (Required for Best Quality)

⚠️ **Important**: The pretrained models (562 MB) must be downloaded manually:

1. **Download**: https://drive.google.com/file/d/1bFwCkjjIbuDkMGkWkUPglZKoP31XTFYZ/view
2. **Extract** the downloaded archive
3. **Place** in `larsnet/pretrained_larsnet_models/`

Expected structure:
```
packaging/lars_service/larsnet/
├── larsnet.py
├── unet.py
├── config.yaml
└── pretrained_larsnet_models/
    ├── kick/pretrained_kick_unet.pth
    ├── snare/pretrained_snare_unet.pth
    ├── toms/pretrained_toms_unet.pth
    ├── hihat/pretrained_hihat_unet.pth
    └── cymbals/pretrained_cymbals_unet.pth
```

### 3. Build the Service

```bash
./build.sh --clean
```

This creates a standalone binary: `dist/lars-service` (~200 MB with models)

## Usage

### From StemSeparator GUI

The LARS service is automatically invoked by StemSeparator when you use the **Drum Details** tab:

1. Load a drum track in StemSeparator
2. Navigate to **🥁 Drum Details** tab
3. Select output directory and options
4. Click **Separate Drum Stems**

### Direct CLI Usage

You can also use the service directly:

```bash
# Activate environment (development only)
conda activate lars-env

# Run separation
dist/lars-service separate \
  --input /path/to/drums.wav \
  --output-dir /path/to/output \
  --stems kick,snare,hihat \
  --device mps \
  --wiener-filter \
  --verbose
```

#### Options

```
--input PATH           Input audio file (required)
--output-dir PATH      Output directory for stems (required)
--stems LIST           Comma-separated list: kick,snare,toms,hihat,cymbals (default: all)
--device DEVICE        Device: auto|mps|cuda|cpu (default: auto)
--wiener-filter        Enable Wiener filtering for better quality
--format FORMAT        Output format: wav|flac|mp3 (default: wav)
--sample-rate RATE     Output sample rate in Hz (default: 44100)
--verbose              Enable verbose logging to stderr
```

### Output Format

The service outputs JSON to stdout with separation results:

```json
{
  "version": "1.0.0",
  "model": "LARS",
  "backend": "mps",
  "stems": {
    "kick": "/output/drums_kick.wav",
    "snare": "/output/drums_snare.wav",
    "hihat": "/output/drums_hihat.wav"
  },
  "wiener_filter": true,
  "processing_time": 3.45,
  "warnings": []
}
```

## Development

### Project Structure

```
packaging/lars_service/
├── src/
│   ├── __main__.py                    # CLI entry point
│   ├── device.py                      # Device detection
│   ├── lars_processor.py              # Placeholder processor
│   ├── lars_processor_demucs.py       # Demucs fallback
│   └── lars_processor_larsnet.py      # LarsNet wrapper (PRIMARY)
├── larsnet/                           # Cloned LarsNet repository
│   ├── larsnet.py                     # Main LarsNet implementation
│   ├── unet.py                        # U-Net architecture
│   ├── config.yaml                    # Model configuration
│   └── pretrained_larsnet_models/     # Model weights (download separately)
├── requirements.txt                   # Python dependencies
├── lars-service.spec                  # PyInstaller configuration
├── build.sh                           # Build script
├── INTEGRATION_GUIDE.md              # Integration documentation
└── README.md                          # This file
```

### Running Tests

```bash
# Activate environment
conda activate lars-env

# Test with a sample file
python -m src separate \
  --input /path/to/test_drums.wav \
  --output-dir /tmp/lars_test \
  --verbose

# Check which processor is being used
# Output will show: [LarsNet (5 U-Nets)] or fallback
```

### Building for Distribution

The LARS service is automatically built when building the main StemSeparator app:

```bash
# From project root
cd packaging/
./build_arm64.sh   # For Apple Silicon
./build_intel.sh   # For Intel Macs
```

The LARS binary is embedded in the main StemSeparator.app bundle.

## Technical Details

### LarsNet Implementation

LarsNet uses a sophisticated architecture:

1. **STFT Processing**: Converts audio to time-frequency domain (4096 FFT, 1024 window)
2. **Parallel U-Nets**: 5 separate U-Net models process magnitude spectrogram
3. **Masking**: Each U-Net outputs a mask for its drum component
4. **Optional Wiener**: Applies α-Wiener filtering to reduce cross-talk
5. **ISTFT**: Converts back to time domain audio

### Performance

- **Speed**: Faster than real-time (processes faster than the audio duration)
- **Quality**: State-of-the-art separation quality
- **Memory**: ~2 GB RAM for model loading + inference
- **Disk**: 562 MB for pretrained models

### Sample Rate Handling

- LarsNet operates at **44100 Hz** internally
- Input audio is automatically resampled if needed
- Output can be resampled to any target sample rate

## Troubleshooting

### "LarsNet not found"

**Cause**: The larsnet repository hasn't been cloned.

**Fix**:
```bash
cd packaging/lars_service/
git clone https://github.com/polimi-ispl/larsnet.git
```

### "Pretrained models not found"

**Cause**: The 562 MB model files haven't been downloaded.

**Fix**: Download from Google Drive link (see Setup section above)

### "Missing model files: ['kick/pretrained_kick_unet.pth', ...]"

**Cause**: Models were partially extracted or in the wrong location.

**Fix**: Ensure the directory structure matches exactly as shown in Setup section.

### Using Demucs/Placeholder Instead of LarsNet

**Cause**: LarsNet failed to load (missing models or import error).

**Check**: Look for error messages in verbose output (`--verbose` flag).

**Verify**: Check the processor being used in the output:
```
[lars-service] Initializing LARS processor on mps [LarsNet (5 U-Nets)]...
```

If it shows a different processor, LarsNet isn't loading correctly.

## Integration with StemSeparator

### From Python

```python
from utils.lars_service_client import separate_drum_stems

result = separate_drum_stems(
    input_path="/path/to/drums.wav",
    output_dir="/path/to/output",
    stems=["kick", "snare", "toms", "hihat", "cymbals"],
    device="auto",
    wiener_filter=True,
    timeout_seconds=300
)

print(f"Stems: {result.stems}")
print(f"Processing time: {result.processing_time}s")
```

## License

- **LARS Service Code**: Same license as StemSeparator
- **LarsNet Model**: CC BY-NC 4.0 (Non-commercial use only)

## References

- **LarsNet Paper**: https://arxiv.org/abs/2310.12286
- **LarsNet Repository**: https://github.com/polimi-ispl/larsnet
- **StemGMD Dataset**: https://zenodo.org/record/6959652

## Support

For issues specific to:
- **LARS Service integration**: Open issue in StemSeparator repository
- **LarsNet model/training**: Refer to original LarsNet repository
