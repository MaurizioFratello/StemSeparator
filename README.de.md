# Stem Separator

<div align="center">

**KI-gestützte Audio Stem Separation mit modernsten Open-Source-Modellen**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/MaurizioFratello/StemSeparator)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://www.apple.com/macos/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[Features](#-features) • [Installation](#-installation) • [Usage](#-verwendung) • [Documentation](#-dokumentation) • [Support](#-support)

</div>

---

## 🎯 Überblick

Stem Separator ist eine professionelle macOS-Anwendung für die KI-gestützte Trennung von Audio-Stems (Vocals, Drums, Bass, etc.) aus Musik-Dateien. Die Anwendung nutzt State-of-the-Art Deep-Learning-Modelle und bietet eine intuitive grafische Benutzeroberfläche.

### ✨ Highlights

- 🎵 **Multiple AI-Modelle**: Mel-Band RoFormer, BS-RoFormer, MDX-Net, Demucs v4
- 🎚️ **Ensemble-Separation**: Kombiniert mehrere Modelle für maximale Qualität
- 🎤 **System Audio Recording**: Direkte Aufnahme von System-Audio (macOS)
- 🎧 **Stem Player**: Echtzeit-Mixing mit individueller Lautstärke-Kontrolle
- ⚡ **GPU-Beschleunigung**: Apple Silicon (MPS) und NVIDIA (CUDA) Support
- 🌍 **Mehrsprachig**: Deutsch und Englisch
- 🎨 **Modernes Dark Theme**: Professionelle, benutzerfreundliche Oberfläche

---

## 🚀 Features

### Audio-Verarbeitung
- **Audio-Datei Upload**: Drag & Drop oder Datei-Browser
- **System Audio Recording**: Aufnahme von System-Audio (macOS mit BlackHole)
- **Automatisches Chunking**: Große Dateien (>30min) werden automatisch in 5-Minuten-Chunks zerlegt
- **Intelligente Fehlerbehandlung**: Automatischer Fallback auf CPU bei GPU-Problemen

### Stem-Separation
- **4-Stem-Modus**: Vocals, Drums, Bass, Other
- **6-Stem-Modus**: Vocals, Drums, Bass, Piano, Guitar, Other
- **2-Stem-Modus**: Vocals, Instrumental (für Karaoke)

### AI-Modelle
- **Mel-Band RoFormer** (~100 MB): Beste Qualität für Vocal Separation
- **BS-RoFormer** (~300 MB): Excellente Qualität, SDX23 Challenge Gewinner
- **MDX-Net (Vocals/Inst)** (~110-120 MB): Spektrogramm CNN, stark für Vocals & Leads
- **Demucs v4** (~240 MB): 6-Stem Separation, Sony MDX Challenge Gewinner
- **Demucs v4 (4-stem)** (~160 MB): Schnelle 4-Stem Separation

### Ensemble-Separation 🆕
- **Balanced Ensemble**: BS-RoFormer + Demucs (2x langsamer, +0.5-0.7 dB SDR)
- **Quality Ensemble**: Mel-RoFormer + BS-RoFormer + Demucs (3x langsamer, +0.8-1.0 dB SDR)
- **Vocals Focus**: Mel-RoFormer + BS-RoFormer (optimal für Karaoke)
- **MDX + Demucs (Vocal Focus)**: MDX-Net Vocals + Demucs (mask blend, weniger Artefakte)

### Stem Player
- **Live-Wiedergabe**: Echtzeit-Mixing separierter Stems
- **Individuelle Kontrollen**: Lautstärke, Mute, Solo pro Stem
- **Master-Volume**: Gesamt-Lautstärke-Kontrolle
- **Position-Seeking**: Präzise Navigation durch das Audio
- **Audio-Export**: Export gemischter Stems

### Weitere Features
- **Queue-System**: Mehrere Dateien nacheinander verarbeiten
- **Native macOS Integration**: Systemmenü, native Dialoge, macOS-Tastaturkürzel
- **Modernes Dark Theme**: Professionelle UI mit Purple-Blue Accents
- **Mehrsprachig**: Deutsch/Englisch mit vollständiger Übersetzung

---

## 📋 Systemanforderungen

### Minimum
- **Betriebssystem**: macOS 10.15 (Catalina) oder neuer
- **Python**: 3.9+ (3.11 empfohlen)
- **RAM**: 8 GB
- **Speicherplatz**: ~1.5 GB für Modelle

### Empfohlen
- **Betriebssystem**: macOS 11.0+ (Big Sur) für Apple Silicon
- **RAM**: 16 GB
- **GPU**: Apple Silicon (M1/M2/M3) für MPS-Beschleunigung oder NVIDIA GPU für CUDA

### Optional (für System Audio Recording)
- **BlackHole 2ch**: Virtuelles Audio-Device (wird automatisch installiert)

---

## 💻 Installation

### Option 1: Standalone macOS Application (Empfohlen für End-User)

**Keine Python-Installation erforderlich!** Lade eine vorgefertigte Anwendung herunter:

1. Lade die passende DMG-Datei für deinen Mac herunter:
   - **Intel Macs**: `StemSeparator-intel.dmg`
   - **Apple Silicon (M1/M2/M3)**: `StemSeparator-arm64.dmg`

2. Öffne die DMG-Datei und ziehe "Stem Separator" in den Applications-Ordner

3. Starte die App (beim ersten Mal: Rechtsklick → "Öffnen" um Gatekeeper zu umgehen)

**Build-Anleitung:** Siehe [PACKAGING.md](PACKAGING.md) für Details zum Erstellen von App-Bundles.

### Option 2: Development Installation (Für Entwickler)

#### 1. Repository klonen

```bash
git clone https://github.com/MaurizioFratello/StemSeparator.git
cd StemSeparator
```

#### 2. Conda Environment erstellen

```bash
# Environment aus environment.yml erstellen
conda env create -f environment.yml

# Environment aktivieren
conda activate stem-separator
```

**Alternative: Manuelle Installation mit Conda**
```bash
# Environment erstellen
conda create -n stem-separator python=3.11

# Environment aktivieren
conda activate stem-separator

# Dependencies installieren
pip install -r requirements.txt
```

#### 3. Modelle vorbereiten (optional)

Die Modelle werden automatisch beim ersten Gebrauch heruntergeladen.
Für manuelles Pre-Download:

```bash
python -c "from core.model_manager import get_model_manager; get_model_manager().download_all_models()"
```

---

## 📖 Verwendung

### App starten

```bash
python main.py
```

### Stem Separation

1. Wählen Sie den **"Upload"** oder **"Recording"** Tab
2. Laden Sie eine Audio-Datei (Drag & Drop) oder starten Sie eine Aufnahme
3. Wählen Sie ein Modell:
   - **Mel-RoFormer**: Beste Qualität für Vocals (empfohlen)
   - **BS-RoFormer**: Excellente Qualität für alle Stems
   - **Demucs v4**: 6-Stem Separation (Piano, Guitar)
   - **Ensemble-Modi**: Maximale Qualität (langsamer)
4. Klicken Sie auf **"Separate"**
5. Stems werden automatisch gespeichert

### Ensemble-Separation

1. Wählen Sie **"Ensemble Mode"** im Upload-Widget
2. Wählen Sie eine Ensemble-Konfiguration:
   - **Balanced**: Beste Balance zwischen Qualität und Geschwindigkeit
   - **Quality**: Maximale Qualität (langsamer)
   - **Vocals Focus**: Optimal für Karaoke
3. Starten Sie die Separation

### Stem Player

1. Wechseln Sie zum **"Player"** Tab
2. Laden Sie separierte Stems (per Verzeichnis oder einzelne Dateien)
3. Nutzen Sie die Mixer-Kontrollen:
   - **M**: Mute (Stem stumm schalten)
   - **S**: Solo (nur diesen Stem hören)
   - **Volume Slider**: Lautstärke pro Stem
   - **Master Volume**: Gesamt-Lautstärke
4. Playback-Kontrollen:
   - Play/Pause/Stop
   - Position-Slider für Seeking
   - Export gemischtes Audio

### System Audio Recording

1. Wechseln Sie zum **"Recording"** Tab
2. Wählen Sie **"In: BlackHole 2ch"** als Eingabegerät
3. Klicken Sie auf **"Start Recording"**
4. Spielen Sie Audio auf Ihrem Mac ab
5. Klicken Sie auf **"Stop & Save"** wenn fertig
6. Die aufgenommene Datei kann direkt für Separation verwendet werden

---

## 🏗️ Projektstruktur

```
StemSeparator/
├── main.py                 # Entry point
├── config.py               # Zentrale Konfiguration
├── requirements.txt        # Dependencies
│
├── core/                   # Business Logic
│   ├── separator.py        # Stem Separation Engine
│   ├── ensemble_separator.py # Ensemble Separation
│   ├── recorder.py         # System Audio Recording
│   ├── player.py           # Stem Player (sounddevice)
│   ├── model_manager.py    # Model Management
│   ├── chunk_processor.py  # Audio Chunking
│   ├── device_manager.py   # GPU/CPU Detection
│   └── blackhole_installer.py
│
├── ui/                     # GUI Components (PySide6)
│   ├── main_window.py      # Main Window
│   ├── app_context.py      # Singleton für Services
│   ├── theme/              # Modern Dark Theme
│   └── widgets/
│       ├── upload_widget.py
│       ├── recording_widget.py
│       ├── queue_widget.py
│       └── player_widget.py
│
├── utils/                  # Utilities
│   ├── logger.py           # Logging System
│   ├── error_handler.py    # Error Handling & Retry
│   ├── i18n.py             # Internationalization
│   └── file_manager.py     # File Operations
│
├── tests/                  # Unit & Integration Tests
│   ├── test_*.py           # Backend Tests
│   └── ui/
│       └── test_*.py       # GUI Tests
│
├── docs/                   # Dokumentation
│   ├── DEVELOPMENT.md      # Entwicklungsdokumentation
│   ├── PROJECT_STATUS.md   # Projekt-Status
│   └── ...
│
└── resources/             # Resources
    ├── translations/      # DE/EN Übersetzungen
    ├── icons/            # UI Icons
    └── models/           # Downloaded Models
```

---

## ⚙️ Konfiguration

Die Hauptkonfiguration befindet sich in `config.py`:

- **Chunk-Größe**: `CHUNK_LENGTH_SECONDS = 300` (5 Minuten)
- **Standard-Modell**: `DEFAULT_MODEL = 'mel-roformer'`
- **Standard-Ensemble**: `DEFAULT_ENSEMBLE_CONFIG = 'balanced'`
- **GPU-Nutzung**: `USE_GPU = True`
- **Log-Level**: `LOG_LEVEL = "INFO"`
- **Standard-Sprache**: `DEFAULT_LANGUAGE = "de"`
- **Sample Rate**: `RECORDING_SAMPLE_RATE = 44100`

---

## 🧪 Tests ausführen

```bash
# Alle Tests
pytest

# Mit Coverage-Report
pytest --cov

# Nur Unit Tests
pytest -m unit

# Nur bestimmte Tests
pytest tests/test_player.py

# GUI Tests
pytest tests/ui/
```

---

## 📚 Dokumentation

- **[DEVELOPMENT.md](docs/DEVELOPMENT.md)**: Technische Entwicklungsdokumentation
- **[PROJECT_STATUS.md](docs/PROJECT_STATUS.md)**: Aktueller Projekt-Status
- **[ENSEMBLE_FEATURE.md](docs/ENSEMBLE_FEATURE.md)**: Ensemble-Separation Feature
- **[PACKAGING.md](PACKAGING.md)**: Packaging-Anleitung
- **[INSTALL_CONDA.md](INSTALL_CONDA.md)**: Detaillierte Conda-Installation

---

## 🔧 Troubleshooting

### "BlackHole not installed"
```bash
brew install blackhole-2ch
```
Die App kann BlackHole auch automatisch installieren.

### "GPU out of memory"
Die App wechselt automatisch zu CPU-Modus. Alternativ:
- Kleinere Audio-Dateien verwenden
- Andere Anwendungen schließen
- Chunk-Größe in `config.py` reduzieren

### "Model download failed"
Manueller Download:
```bash
python -c "from core.model_manager import get_model_manager; get_model_manager().download_model('mel-roformer')"
```

### Kein Audio bei Stem-Wiedergabe
Stellen Sie sicher, dass:
- `sounddevice` installiert ist: `pip install sounddevice`
- Das richtige Audio-Gerät in macOS Systemeinstellungen ausgewählt ist
- Die Lautsprecher nicht stumm geschaltet sind

### Logs prüfen
Logs werden gespeichert in `logs/app.log` mit automatischer Rotation:
- **DEBUG**: Detaillierte Debug-Informationen
- **INFO**: Normale Operationen (Standard)
- **WARNING**: Warnungen ohne Funktionsverlust
- **ERROR**: Fehler mit Stack-Traces

Log-Level kann in `config.py` angepasst werden.

---

## 🎓 Entwicklung

### Code-Style
```bash
black .
flake8 .
```

### Tests hinzufügen
Neue Tests in `tests/` Verzeichnis erstellen mit Präfix `test_`.

**Best Practices:**
- Unit Tests für isolierte Komponenten
- Integration Tests für UI-Komponenten
- Mock externe Dependencies (Audio-Devices, File I/O)

### Neue Übersetzungen
Keys in `resources/translations/de.json` und `en.json` hinzufügen.

---

## 📝 Changelog

### v1.0.0 (November 2025)
- ✅ Ensemble-Separation Feature (Balanced, Quality, Vocals Focus)
- ✅ Modernes Dark Theme mit Purple-Blue Accents
- ✅ Native macOS Integration (Systemmenü, native Dialoge)
- ✅ Migration von rtmixer zu sounddevice für Stem Player
- ✅ Behebung von Deadlocks beim Stop/Pause
- ✅ Verbesserte Fehlerbehandlung mit detaillierten Meldungen
- ✅ Umfassende Tests für alle Komponenten
- ✅ Vollständige Dokumentation

### v1.0.0-rc1 (November 2025)
- Initiale Release Candidate
- Alle Basis-Features implementiert
- Umfassende Test-Coverage

---

## 🗺️ Roadmap

- [ ] Windows/Linux Support für System Audio Recording
- [ ] Weitere Modelle (MDX-Net, VR Architecture, etc.)
- [ ] Batch-Export-Funktionalität
- [ ] Real-time Preview während Verarbeitung
- [ ] Custom Model Training Interface
- [ ] VST/AU Plugin Version
- [ ] Cloud-basierte Verarbeitung (optional)
- [ ] Mobile App (iOS/Android)

---

## 📄 Lizenz

Dieses Projekt verwendet Open-Source-Modelle:
- **Mel-Band RoFormer**: Open Source
- **BS-RoFormer**: Open Source
- **Demucs**: MIT License
- **sounddevice**: MIT License
- **PySide6**: LGPL License

---

## 🙏 Credits

- **audio-separator**: Python-Bibliothek für Stem Separation
- **Demucs**: Facebook Research (Meta AI)
- **BS-RoFormer**: ByteDance AI Lab
- **Mel-Band RoFormer**: Music Source Separation Community
- **PySide6**: Qt for Python
- **sounddevice**: Python bindings for PortAudio
- **BlackHole**: Existential Audio Inc.

---

## 💬 Support

Bei Problemen:
1. Logs in `logs/app.log` prüfen
2. [Issue auf GitHub erstellen](https://github.com/MaurizioFratello/StemSeparator/issues) mit:
   - Fehlerbeschreibung
   - Relevante Log-Auszüge
   - System-Informationen (OS, Python-Version)
3. Debugging mit `LOG_LEVEL = "DEBUG"` in config.py

---

<div align="center">

**Version**: 1.0.0  
**Entwickelt mit**: Python, PySide6, PyTorch, sounddevice, audio-separator  
**Maintainer**: Moritz Bruder  
**Repository**: [https://github.com/MaurizioFratello/StemSeparator](https://github.com/MaurizioFratello/StemSeparator)

Made with ❤️ for the music community

</div>
