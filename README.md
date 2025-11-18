# Stem Separator

KI-gestützte Audio Stem Separation mit modernsten Open-Source-Modellen.

**Status**: ✅ **v1.0.0 - Produktionsreif!** (Stand: 17. November 2024)

## Features

- **Audio-Datei Upload**: Drag & Drop oder Datei-Browser
- **System Audio Recording**: Aufnahme von System-Audio (macOS mit BlackHole)
- **Multiple Stem-Konfigurationen**:
  - 4-Stem: Vocals, Drums, Bass, Other
  - 6-Stem: Vocals, Drums, Bass, Piano, Guitar, Other
- **State-of-the-Art Modelle**:
  - Mel-Band RoFormer (beste Qualität)
  - BS-RoFormer (excellente Qualität)
  - Demucs v4 (balanced, 4-stem und 6-stem)
- **Intelligente Verarbeitung**:
  - Automatisches Chunking für große Dateien (5min Chunks)
  - GPU-Beschleunigung (MPS für Apple Silicon, CUDA für NVIDIA)
  - Automatischer Fallback auf CPU bei Problemen
  - Retry-Logik mit verschiedenen Strategien
- **Stem Player mit Echtzeit-Mixing**:
  - Live-Wiedergabe separierter Stems
  - Individuelle Lautstärke-Kontrolle pro Stem
  - Mute/Solo Funktionen
  - Master-Volume-Kontrolle
  - Position-Seeking mit Slider
  - Audio-Export der gemischten Stems
- **Queue-System**: Mehrere Dateien nacheinander verarbeiten
- **Mehrsprachig**: Deutsch/Englisch

## Systemanforderungen

- **Betriebssystem**: macOS (Apple Silicon empfohlen für GPU-Beschleunigung)
- **Python**: 3.9+ (3.11 empfohlen)
- **RAM**: 8 GB Minimum (16 GB empfohlen)
- **Speicherplatz**: ~1.5 GB für Modelle
- **Audio**: PortAudio für Wiedergabe (automatisch installiert)

### Für System Audio Recording (optional):
- BlackHole (virtuelles Audio-Device)
- Wird automatisch installiert wenn nicht vorhanden

## Installation

### Option 1: Standalone macOS Application (Recommended for End Users)

**No Python installation required!** Download a pre-built application bundle:

1. Download the appropriate DMG for your Mac:
   - **Intel Macs**: `StemSeparator-intel.dmg`
   - **Apple Silicon (M1/M2/M3)**: `StemSeparator-arm64.dmg`

2. Open the DMG file and drag "Stem Separator" to your Applications folder

3. Launch the app (first time: right-click → "Open" to bypass Gatekeeper)

**Building from source:** See [PACKAGING.md](PACKAGING.md) for instructions on creating standalone app bundles.

### Option 2: Development Installation (For Developers)

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

## Verwendung

### App starten

```bash
python main.py
```

### Stem Separation
1. Wählen Sie "Upload" oder "Recording" Tab
2. Laden Sie eine Audio-Datei oder starten Sie eine Aufnahme
3. Wählen Sie ein Modell (Mel-RoFormer empfohlen für beste Qualität)
4. Klicken Sie auf "Separate"
5. Stems werden automatisch gespeichert

### Stem Player
1. Wechseln Sie zum "Player" Tab
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

### Tests ausführen

```bash
# Alle Tests
pytest

# Mit Coverage-Report
pytest --cov

# Nur Unit Tests
pytest -m unit

# Nur bestimmte Tests
pytest tests/test_player.py
```

## Projektstruktur

```
StemSeparator/
├── main.py                 # Entry point
├── config.py               # Zentrale Konfiguration
├── requirements.txt        # Dependencies
│
├── ui/                     # GUI Components (PySide6)
│   ├── main_window.py
│   ├── app_context.py      # Singleton für Services
│   └── widgets/
│       ├── upload_widget.py
│       ├── recording_widget.py
│       ├── queue_widget.py
│       └── player_widget.py
│
├── core/                   # Business Logic
│   ├── separator.py        # Stem Separation Engine
│   ├── recorder.py         # System Audio Recording
│   ├── player.py           # Stem Player (sounddevice)
│   ├── queue_manager.py    # Task Queue
│   ├── model_manager.py    # Model Management
│   ├── chunk_processor.py  # Audio Chunking
│   └── blackhole_installer.py
│
├── utils/                  # Utilities
│   ├── logger.py           # Logging System
│   ├── error_handler.py    # Error Handling & Retry
│   ├── i18n.py             # Internationalization
│   └── file_manager.py
│
├── tests/                  # Unit & Integration Tests
│   ├── test_logger.py
│   ├── test_error_handler.py
│   ├── test_player.py
│   └── ui/
│       └── test_player_widget.py
│
└── resources/             # Resources
    ├── translations/      # DE/EN Übersetzungen
    ├── icons/            # UI Icons
    └── models/           # Downloaded Models
```

## Konfiguration

Die Hauptkonfiguration befindet sich in `config.py`:

- **Chunk-Größe**: `CHUNK_LENGTH_SECONDS = 300` (5 Minuten)
- **Standard-Modell**: `DEFAULT_MODEL = 'mel-roformer'`
- **GPU-Nutzung**: `USE_GPU = True`
- **Log-Level**: `LOG_LEVEL = "INFO"`
- **Standard-Sprache**: `DEFAULT_LANGUAGE = "de"`
- **Sample Rate**: `RECORDING_SAMPLE_RATE = 44100`

## Verwendete Modelle

### Mel-Band RoFormer
- **Größe**: ~100 MB
- **Stems**: 2 (Vocals, Instrumental)
- **Qualität**: Beste verfügbare Qualität für Vocal Separation
- **Geschwindigkeit**: Schnell
- **Verwendung**: Optimal für reine Vocal-Isolation
- **Status**: State-of-the-art für Vocal Separation

### BS-RoFormer
- **Größe**: ~300 MB
- **Stems**: 2 (Vocals, Instrumental)
- **Qualität**: Excellente Qualität für Vocal Separation
- **Geschwindigkeit**: Mittel
- **Verwendung**: Hochwertige Vocal-Isolation
- **Status**: SDX23 Challenge Gewinner

### Demucs v4 (htdemucs_6s)
- **Größe**: ~240 MB
- **Stems**: 6 (Vocals, Drums, Bass, Piano, Guitar, Other)
- **Qualität**: Sehr gut
- **Geschwindigkeit**: Balanced
- **Status**: Sony MDX Challenge Gewinner

### Demucs v4 (htdemucs)
- **Größe**: ~160 MB
- **Stems**: 4 (Vocals, Drums, Bass, Other)
- **Qualität**: Sehr gut
- **Geschwindigkeit**: Schnell

## Audio-Wiedergabe Technologie

Die Stem Player-Komponente verwendet **sounddevice** für zuverlässige Audio-Wiedergabe:

- **Pre-loaded Audio**: Alle Stems werden vor der Wiedergabe in den Speicher geladen
- **Echtzeit-Mixing**: Stems werden im Speicher gemischt mit individuellen Einstellungen
- **Non-blocking Playback**: UI bleibt während Wiedergabe responsive
- **Position Tracking**: Separater Thread für präzise Position-Updates

### Migration von rtmixer zu sounddevice

Version 1.0.0 migriert von `rtmixer.RingBuffer` zu `sounddevice.play()`:
- **Einfacherer Code**: -65 Zeilen, bessere Wartbarkeit
- **Zuverlässigere Wiedergabe**: Optimiert für pre-loaded Audio
- **Keine Streaming-Komplexität**: Kein RingBuffer-Management erforderlich
- **Bewährte Lösung**: Standard-Ansatz für Python Audio-Wiedergabe

## Bekannte Limitierungen

- System Audio Recording nur auf macOS (erfordert BlackHole)
- Sehr große Dateien (>30min) werden automatisch in Chunks zerlegt
- GPU-Verarbeitung erfordert Apple Silicon Mac (MPS) oder NVIDIA GPU (CUDA)
- Erste Verarbeitung langsamer (Model Loading)

## Troubleshooting

### "BlackHole not installed"
```bash
brew install blackhole-2ch
```

### "GPU out of memory"
Die App wechselt automatisch zu CPU-Modus. Alternativ:
- Kleinere Audio-Dateien verwenden
- Andere Anwendungen schließen

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

### Application Freeze beim Stop
Wurde in v1.0.0 behoben:
- Deadlock-Prävention in Thread-Synchronisation
- Callback-Handling außerhalb Worker-Threads
- Korrekte Reihenfolge: stop → cancel → thread join → callback

## Logs

Logs werden gespeichert in `logs/app.log` mit automatischer Rotation:
- **DEBUG**: Detaillierte Debug-Informationen
- **INFO**: Normale Operationen (Standard)
- **WARNING**: Warnungen ohne Funktionsverlust
- **ERROR**: Fehler mit Stack-Traces

Log-Level kann in `config.py` angepasst werden.

## Entwicklung

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

## Lizenz

Dieses Projekt verwendet Open-Source-Modelle:
- **Mel-Band RoFormer**: [Lizenz Info]
- **BS-RoFormer**: [Lizenz Info]
- **Demucs**: MIT License
- **sounddevice**: MIT License

## Credits

- **audio-separator**: Python-Bibliothek für Stem Separation
- **Demucs**: Facebook Research (Meta AI)
- **BS-RoFormer**: ByteDance AI Lab
- **Mel-Band RoFormer**: Music Source Separation Community
- **PySide6**: Qt for Python
- **sounddevice**: Python bindings for PortAudio
- **BlackHole**: Existential Audio Inc.

## Support

Bei Problemen:
1. Logs in `logs/app.log` prüfen
2. Issue auf GitHub erstellen mit:
   - Fehlerbeschreibung
   - Relevante Log-Auszüge
   - System-Informationen (OS, Python-Version)
3. Debugging mit `LOG_LEVEL = "DEBUG"` in config.py

## Changelog

### v1.0.0 (17. November 2024)
- ✅ Migration von rtmixer zu sounddevice für Stem Player
- ✅ Behebung von Deadlocks beim Stop/Pause
- ✅ Verbesserte Fehlerbehandlung mit detaillierten Meldungen
- ✅ Code-Vereinfachung (-65 Zeilen)
- ✅ Konsistente Dokumentation und Kommentare
- ✅ Umfassende Tests für Player-Komponente

### v1.0.0-rc1 (9. November 2024)
- Initiale Release Candidate
- Alle Basis-Features implementiert
- Umfassende Test-Coverage

## Roadmap

- [ ] Windows/Linux Support für System Audio Recording
- [ ] Weitere Modelle (MDX-Net, VR Architecture, etc.)
- [ ] Batch-Export-Funktionalität
- [ ] Real-time Preview während Verarbeitung
- [ ] Custom Model Training Interface
- [ ] VST/AU Plugin Version
- [ ] Cloud-basierte Verarbeitung (optional)
- [ ] Mobile App (iOS/Android)

---

**Version**: 1.0.0
**Entwickelt mit**: Python, PySide6, PyTorch, sounddevice, audio-separator
**Maintainer**: Moritz Bruder
**Repository**: https://github.com/MaurizioFratello/StemSeparator
