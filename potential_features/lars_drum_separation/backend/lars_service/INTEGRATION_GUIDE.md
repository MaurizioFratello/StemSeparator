# LarsNet Integration Guide

## Overview

LarsNet is a deep learning model from Politecnico di Milano for drum source separation using 5 parallel U-Nets.

**Repository**: https://github.com/polimi-ispl/larsnet

## Integration Status

✅ **INTEGRATION COMPLETE** - LarsNet is now fully integrated into the LARS service!

### What's Been Done

1. ✅ Cloned LarsNet repository to `packaging/lars_service/larsnet/`
2. ✅ Created `lars_processor_larsnet.py` wrapping the actual LarsNet implementation
3. ✅ Updated `__main__.py` to prioritize LarsNet over fallback processors
4. ✅ Updated PyInstaller spec to bundle LarsNet code and models
5. ✅ All dependencies already in `requirements.txt`

### What's Still Needed

⚠️ **PRETRAINED MODELS** - The 562 MB model files must be downloaded manually:

1. Download from: https://drive.google.com/file/d/1bFwCkjjIbuDkMGkWkUPglZKoP31XTFYZ/view
2. Extract the downloaded file (562 MB)
3. Place in `packaging/lars_service/larsnet/pretrained_larsnet_models/`

Expected structure:
```
larsnet/pretrained_larsnet_models/
  ├── kick/pretrained_kick_unet.pth
  ├── snare/pretrained_snare_unet.pth
  ├── toms/pretrained_toms_unet.pth
  ├── hihat/pretrained_hihat_unet.pth
  └── cymbals/pretrained_cymbals_unet.pth
```

### Building with LarsNet

```bash
cd packaging/lars_service/
./build.sh --clean
```

**Note**: The build will succeed even without the pretrained models. At runtime:
- **With models**: Uses actual LarsNet (5 U-Nets) ✨
- **Without models**: Falls back to Demucs workaround or placeholder

## Testing LarsNet Integration

### Using LARS Service CLI

```bash
cd packaging/lars_service/
conda activate lars-env

# Test separation (requires models to be downloaded)
dist/lars-service separate \
  --input /path/to/drums.wav \
  --output-dir /tmp/lars_test \
  --device mps \
  --wiener-filter \
  --verbose
```

### Using LarsNet Directly (Development)

For development/testing, you can also use LarsNet directly:

```bash
cd packaging/lars_service/larsnet/
python separate.py -i /path/to/drums.wav -o /output/dir -w 1.0 -d mps
```

Options:
- `-i`: Input audio file(s) or directory
- `-o`: Output directory (default: `separated_stems/`)
- `-w`: Wiener filter exponent (positive float, default: no filtering)
- `-d`: Device (cpu, cuda:0, mps)

## Integration Architecture

```
LARS Service
    ↓
lars_processor.py
    ↓
larsnet/larsnet.py
    ↓
5 Parallel U-Nets
    ├─→ Kick U-Net
    ├─→ Snare U-Net
    ├─→ Toms U-Net
    ├─→ Hi-hat U-Net
    └─→ Cymbals U-Net
    ↓
5 Separated Stems + Optional Wiener Filtering
```

## Model Details

- **Size**: 562 MB (pretrained weights)
- **Architecture**: 5 parallel U-Nets
- **Speed**: Faster than real-time
- **Dataset**: StemGMD (1,224 hours of drums)
- **License**: CC BY-NC 4.0

## Processor Priority

The LARS service now uses this priority order:

1. **LarsNet** (5 U-Nets) - BEST - If models are downloaded
2. **Demucs** (frequency filtering workaround) - GOOD - If LarsNet unavailable
3. **Placeholder** (gain-based) - TESTING ONLY - If both unavailable

You can check which processor is being used in the verbose output:
```
[lars-service] Initializing LARS processor on mps [LarsNet (5 U-Nets)]...
```

## Implementation Details

### Key Files

- `src/lars_processor_larsnet.py` - LarsNet wrapper (273 lines)
- `src/__main__.py` - CLI with automatic fallback logic
- `lars-service.spec` - PyInstaller config with LarsNet bundling
- `larsnet/` - Cloned LarsNet repository

### How It Works

1. **Model Loading**: `lars_processor_larsnet.py` loads all 5 U-Net models on initialization
2. **Separation**: Calls `LarsNet.forward()` which handles:
   - Audio loading and resampling to 44100 Hz
   - Parallel inference through 5 U-Nets
   - Optional α-Wiener filtering for cross-talk reduction
3. **Output**: Returns dict of `{stem_name: torch.Tensor}` which we save as audio files

### Error Handling

The processor provides helpful error messages:
- Missing LarsNet repository → Instructions to clone
- Missing pretrained models → Instructions to download with Google Drive link
- Missing individual model files → Lists which files are missing
