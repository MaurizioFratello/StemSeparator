# Stem Separator

<div align="center">

**AI-Powered Audio Stem Separation with State-of-the-Art Open Source Models**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/MaurizioFratello/StemSeparator)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Documentation](#-documentation) • [Support](#-support)

</div>

---

## 🎯 Overview

Stem Separator is a desktop application for AI-powered separation of audio stems (vocals, drums, bass, etc.) from music files. The application uses state-of-the-art deep learning models and provides an intuitive graphical user interface.

### ✨ Highlights

- 🎵 **Multiple AI Models**: Mel-Band RoFormer, BS-RoFormer, MDX-Net, Demucs v4
- 🎚️ **Ensemble Separation**: Combines multiple models for maximum quality
- 🎤 **System Audio Recording**: Direct recording of system audio (macOS)
- 🎧 **Stem Player**: Real-time mixing with individual volume control
- ⚡ **GPU Acceleration**: Apple Silicon (MPS) and NVIDIA (CUDA) support
- 🌍 **Multilingual**: German and English
- 🎨 **Modern Dark Theme**: Professional, user-friendly interface

---

## 🚀 Features

### Audio Processing
- **Audio File Upload**: Drag & drop or file browser
- **System Audio Recording**: Native macOS system audio recording (ScreenCaptureKit on macOS 13+, BlackHole fallback)
- **Automatic Chunking**: Large files (>30min) automatically split into 5-minute chunks
- **Intelligent Error Handling**: Automatic CPU fallback on GPU issues

### Stem Separation
- **4-Stem Mode**: Vocals, Drums, Bass, Other
- **6-Stem Mode**: Vocals, Drums, Bass, Piano, Guitar, Other
- **2-Stem Mode**: Vocals, Instrumental (for karaoke)

### AI Models
- **Mel-Band RoFormer** (~100 MB): Best quality for vocal separation
- **BS-RoFormer** (~300 MB): Excellent quality, SDX23 Challenge winner
- **MDX-Net (Vocals/Inst)** (~110-120 MB): Spectrogram CNN, strong for vocals & leads
- **Demucs v4** (~240 MB): 6-stem separation, Sony MDX Challenge winner
- **Demucs v4 (4-stem)** (~160 MB): Fast 4-stem separation

### Ensemble Separation 🆕
- **Balanced Ensemble**: Staged approach - Mel-RoFormer + MDX Vocals + Demucs (vocals), then Demucs (residual) (~2x slower, +0.5-0.7 dB SDR)
- **Quality Ensemble**: Staged approach - Mel-RoFormer + MDX Vocals + Demucs (vocals), then Demucs + BS-RoFormer (residual) (~2.5x slower, +0.8 dB SDR)
- **Ultra Ensemble**: Maximum quality staged processing (~3.5x slower, +1.0 dB SDR)

### Stem Player
- **Live Playback**: Real-time mixing of separated stems
- **Individual Controls**: Volume, mute, solo per stem
- **Master Volume**: Overall volume control
- **Position Seeking**: Precise navigation through audio
- **Audio Export**: Export mixed stems

### Additional Features
- **Queue System**: Process multiple files sequentially
- **Native macOS Integration**: System menu, native dialogs, macOS keyboard shortcuts
- **Modern Dark Theme**: Professional UI with purple-blue accents
- **Multilingual**: German/English with full translation

---

## 📋 System Requirements

### Minimum
- **Operating System**: macOS 10.15 (Catalina) or newer
- **Python**: 3.10+ (3.11 recommended, 3.9 supported with compatibility layer)
- **RAM**: 8 GB
- **Storage**: ~1.5 GB for models

### Recommended
- **Operating System**: macOS 11.0+ (Big Sur) for Apple Silicon
- **RAM**: 16 GB
- **GPU**: Apple Silicon (M1/M2/M3) for MPS acceleration or NVIDIA GPU for CUDA

### Optional (for System Audio Recording on older macOS)
- **BlackHole 2ch**: Virtual audio device (fallback for macOS < 13.0, automatically installed if needed)
- **Screen Recording Permission**: Required for ScreenCaptureKit on macOS 13+ (native, no driver needed)

---

## 💻 Installation

### Option 1: Standalone macOS Application (Recommended for End Users)

**No Python installation required!** Download a pre-built application:

1. Download the DMG file for your Mac from the [Releases page](https://github.com/MaurizioFratello/StemSeparator/releases):
   - **Apple Silicon (M1/M2/M3)**: `StemSeparator-arm64.dmg`
   - **Intel Macs**: Currently not available (Intel build in development)

2. Open the DMG file and drag "Stem Separator" to the Applications folder

3. Launch the app (first time: right-click → "Open" to bypass Gatekeeper)

**Build Instructions:** See [docs/PACKAGING.md](docs/PACKAGING.md) for details on creating app bundles.

### Option 2: Development Installation (For Developers)

#### 1. Clone Repository

```bash
git clone https://github.com/MaurizioFratello/StemSeparator.git
cd StemSeparator
```

#### 2. Create Conda Environment

```bash
# Create environment from environment.yml
conda env create -f environment.yml

# Activate environment
conda activate stem-separator
```

**Alternative: Manual Installation with Conda**
```bash
# Create environment
conda create -n stem-separator python=3.11

# Activate environment
conda activate stem-separator

# Install dependencies
pip install -r requirements.txt
```

#### 3. Prepare Models (Optional)

Models are automatically downloaded on first use.
For manual pre-download:

```bash
python -c "from core.model_manager import get_model_manager; get_model_manager().download_all_models()"
```

---

## 📖 Usage

### Starting the App

```bash
python main.py
```

### Stem Separation

1. Select the **"Upload"** or **"Recording"** tab
2. Load an audio file (drag & drop) or start a recording
3. Choose a model:
   - **Mel-RoFormer**: Best quality for vocals (recommended)
   - **BS-RoFormer**: Excellent quality for all stems
   - **Demucs v4**: 6-stem separation (piano, guitar)
   - **Ensemble Modes**: Maximum quality (slower)
4. Click **"Separate"**
5. Stems are automatically saved

### Ensemble Separation

1. Select **"Ensemble Mode"** in the upload widget
2. Choose an ensemble configuration:
   - **Balanced**: Recommended - Good quality, reasonable processing time (~2x)
   - **Quality**: Professional quality - Best balance of quality/time (~2.5x)
   - **Ultra**: Maximum quality for critical applications (~3.5x)
3. Start separation

**Note:** Ensemble separation uses a staged approach: vocals are separated first using multiple models, then residual stems (drums, bass, other) are processed separately for optimal quality.

### Stem Player

1. Switch to the **"Player"** tab
2. Load separated stems (by directory or individual files)
3. Use mixer controls:
   - **M**: Mute (silence stem)
   - **S**: Solo (hear only this stem)
   - **Volume Slider**: Volume per stem
   - **Master Volume**: Overall volume
4. Playback controls:
   - Play/Pause/Stop
   - Position slider for seeking
   - Export mixed audio

### System Audio Recording

**macOS 13+ (Ventura and later):**
1. Switch to the **"Recording"** tab
2. Grant **Screen Recording permission** when prompted (System Settings → Privacy & Security)
3. Click **"Start Recording"** (uses native ScreenCaptureKit - no driver needed)
4. Play audio on your Mac
5. Click **"Stop & Save"** when finished

**macOS 12 and earlier:**
1. Switch to the **"Recording"** tab
2. Select **"In: BlackHole 2ch"** as input device (BlackHole will be installed automatically if needed)
3. Click **"Start Recording"**
4. Play audio on your Mac
5. Click **"Stop & Save"** when finished

The recorded file can be directly used for separation.

---

## 🏗️ Project Structure

```
StemSeparator/
├── main.py                 # Entry point
├── config.py               # Central configuration
├── requirements.txt        # Dependencies
│
├── core/                   # Business logic
│   ├── separator.py        # Stem separation engine
│   ├── ensemble_separator.py # Ensemble separation
│   ├── recorder.py         # System audio recording
│   ├── screencapture_recorder.py # ScreenCaptureKit recording
│   ├── player.py           # Stem player (sounddevice)
│   ├── model_manager.py    # Model management
│   ├── chunk_processor.py  # Audio chunking
│   ├── device_manager.py   # GPU/CPU detection
│   ├── separation_subprocess.py # Subprocess separation
│   ├── sampler_export.py   # Loop/sampler export
│   └── blackhole_installer.py
│
├── ui/                     # GUI components (PySide6)
│   ├── main_window.py      # Main window
│   ├── app_context.py      # Singleton for services
│   ├── theme/              # Modern dark theme
│   └── widgets/
│       ├── upload_widget.py
│       ├── recording_widget.py
│       ├── queue_widget.py
│       ├── player_widget.py
│       ├── export_loops_widget.py
│       ├── export_mixed_widget.py
│       └── settings_dialog.py
│
├── utils/                  # Utilities
│   ├── logger.py           # Logging system
│   ├── error_handler.py    # Error handling & retry
│   ├── i18n.py             # Internationalization
│   ├── file_manager.py     # File operations
│   ├── beat_detection.py  # Beat detection
│   ├── audio_processing.py # Audio utilities
│   └── macos_integration.py # macOS-specific features
│
├── tests/                  # Unit & integration tests
│   ├── test_*.py           # Backend tests
│   └── ui/
│       └── test_*.py       # GUI tests
│
├── docs/                   # Documentation
│   ├── DEVELOPMENT.md      # Development documentation
│   ├── PROJECT_STATUS.md   # Project status
│   └── ...
│
└── resources/             # Resources
    ├── translations/      # DE/EN translations
    ├── icons/            # UI icons
    └── models/           # Downloaded models
```

---

## ⚙️ Configuration

Main configuration is located in `config.py`:

- **Chunk Size**: `CHUNK_LENGTH_SECONDS = 300` (5 minutes)
- **Default Model**: `DEFAULT_MODEL = 'demucs_6s'`
- **Default Ensemble**: `DEFAULT_ENSEMBLE_CONFIG = 'balanced_staged'`
- **GPU Usage**: `USE_GPU = True`
- **Log Level**: `LOG_LEVEL = "INFO"`
- **Default Language**: `DEFAULT_LANGUAGE = "de"` (change to `"en"` for English)
- **Sample Rate**: `RECORDING_SAMPLE_RATE = 44100`

---

## 🧪 Running Tests

```bash
# All tests
pytest

# With coverage report
pytest --cov

# Only unit tests
pytest -m unit

# Only specific tests
pytest tests/test_player.py

# GUI tests
pytest tests/ui/
```

---

## 📚 Documentation

- **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**: Comprehensive user guide for end users
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**: Technical development documentation
- **[docs/ENSEMBLE_FEATURE.md](docs/ENSEMBLE_FEATURE.md)**: Ensemble separation feature
- **[docs/PACKAGING.md](docs/PACKAGING.md)**: Packaging guide
- **[docs/INSTALL_CONDA.md](docs/INSTALL_CONDA.md)**: Detailed Conda installation
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: Contribution guidelines
- **[CHANGELOG.md](CHANGELOG.md)**: Version history

---

## 🔧 Troubleshooting

### "No recording backend available"

**For macOS 13+ (Ventura and later):**
- Grant **Screen Recording permission** in System Settings → Privacy & Security → Screen Recording
- The app uses native ScreenCaptureKit (no driver installation needed)

**For macOS 12 and earlier:**
- Install BlackHole: `brew install blackhole-2ch`
- The app can also install BlackHole automatically

### "GPU out of memory"
The app automatically switches to CPU mode. Alternatively:
- Use smaller audio files
- Close other applications
- Reduce chunk size in `config.py`

### "Model download failed"
Manual download:
```bash
python -c "from core.model_manager import get_model_manager; get_model_manager().download_model('mel-roformer')"
```

### No audio during stem playback
Ensure that:
- `sounddevice` is installed: `pip install sounddevice`
- The correct audio device is selected in macOS system settings
- Speakers are not muted

### Check Logs
Logs are saved in `logs/app.log` with automatic rotation:
- **DEBUG**: Detailed debug information
- **INFO**: Normal operations (default)
- **WARNING**: Warnings without loss of functionality
- **ERROR**: Errors with stack traces

Log level can be adjusted in `config.py`.

---

## 🎓 Development

### Code Style
```bash
black .
flake8 .
```

### Adding Tests
Create new tests in the `tests/` directory with `test_` prefix.

**Best Practices:**
- Unit tests for isolated components
- Integration tests for UI components
- Mock external dependencies (audio devices, file I/O)

### New Translations
Add keys to `resources/translations/de.json` and `en.json`.

---

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

### v1.0.0 (December 2024)
- ✅ Ensemble separation feature (Balanced, Quality, Vocals Focus)
- ✅ Modern dark theme with purple-blue accents
- ✅ Native macOS integration (system menu, native dialogs)
- ✅ Migration from rtmixer to sounddevice for stem player
- ✅ Fixed deadlocks on stop/pause
- ✅ Improved error handling with detailed messages
- ✅ Comprehensive tests for all components
- ✅ Complete documentation

---

## 🗺️ Roadmap

- [ ] Windows/Linux support for system audio recording
- [ ] Additional models (MDX-Net variations, VR Architecture, etc.)
- [ ] Batch export functionality
- [ ] Real-time preview during processing
- [ ] Custom model training interface
- [ ] VST/AU plugin version
- [ ] Cloud-based processing (optional)
- [ ] Mobile app (iOS/Android)

---

## 📄 License

This project uses open source models:
- **Mel-Band RoFormer**: Open Source
- **BS-RoFormer**: Open Source
- **Demucs**: MIT License
- **sounddevice**: MIT License
- **PySide6**: LGPL License

See [LICENSE](LICENSE) file for details.

---

## 🙏 Credits

- **audio-separator**: Python library for stem separation
- **Demucs**: Facebook Research (Meta AI)
- **BS-RoFormer**: ByteDance AI Lab
- **Mel-Band RoFormer**: Music Source Separation Community
- **PySide6**: Qt for Python
- **sounddevice**: Python bindings for PortAudio
- **BlackHole**: Existential Audio Inc.

---

## 💬 Support

For issues:
1. Check logs in `logs/app.log`
2. [Create an issue on GitHub](https://github.com/MaurizioFratello/StemSeparator/issues) with:
   - Error description
   - Relevant log excerpts
   - System information (OS, Python version)
3. Debug with `LOG_LEVEL = "DEBUG"` in config.py

---

## 🌍 Languages

- [English](README.md) (this file)
- [Deutsch](README.de.md)

---

<div align="center">

**Version**: 1.0.0
**Built with**: Python, PySide6, PyTorch, sounddevice, audio-separator
**Maintainer**: Moritz Bruder
**Repository**: [https://github.com/MaurizioFratello/StemSeparator](https://github.com/MaurizioFratello/StemSeparator)

Made with ❤️ for the music community

</div>
