"""
Zentrale Konfiguration für Stem Separator
"""
import os
from pathlib import Path

# Basis-Pfade
BASE_DIR = Path(__file__).parent
RESOURCES_DIR = BASE_DIR / "resources"
MODELS_DIR = RESOURCES_DIR / "models"
TRANSLATIONS_DIR = RESOURCES_DIR / "translations"
ICONS_DIR = RESOURCES_DIR / "icons"
LOGS_DIR = BASE_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"

# Erstelle Verzeichnisse falls nicht vorhanden
for directory in [MODELS_DIR, LOGS_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Chunking-Konfiguration
CHUNK_LENGTH_SECONDS = 300  # 5 Minuten
CHUNK_OVERLAP_SECONDS = 2   # 2 Sekunden Overlap für nahtloses Merging
MIN_CHUNK_LENGTH = 150      # Minimale Chunk-Länge bei Fallback (2.5 min)

# Audio-Konfiguration
SUPPORTED_AUDIO_FORMATS = ['.wav', '.mp3', '.flac', '.m4a', '.ogg', '.aac']
DEFAULT_SAMPLE_RATE = 44100
EXPORT_SAMPLE_RATE = 44100
EXPORT_BIT_DEPTH = 16  # 16, 24, oder 32 bit

# Model-Konfiguration
# model_filename entspricht dem audio-separator Modell-Dateinamen
MODELS = {
    'bs-roformer': {
        'name': 'BS-RoFormer',
        'stems': 4,
        'size_mb': 300,
        'description': 'Best quality, slower processing',
        'model_filename': 'model_bs_roformer_ep_317_sdr_12.9755.ckpt'  # Standard BS-RoFormer
    },
    'demucs_6s': {
        'name': 'Demucs v4 (6-stem)',
        'stems': 6,
        'size_mb': 240,
        'description': 'Vocals, Drums, Bass, Piano, Guitar, Other',
        'model_filename': 'htdemucs_6s.yaml'
    },
    'demucs_4s': {
        'name': 'Demucs v4 (4-stem)',
        'stems': 4,
        'size_mb': 160,
        'description': 'Vocals, Drums, Bass, Other - balanced',
        'model_filename': 'htdemucs.yaml'
    }
}

# Default Model
DEFAULT_MODEL = 'demucs_6s'

# Quality Presets für Separation
# Diese beeinflussen die Qualität und Geschwindigkeit der Stem-Trennung
QUALITY_PRESETS = {
    'fast': {
        'name': 'Fast',
        'description': 'Schnellere Verarbeitung, geringere Qualität',
        'params': {
            # Gemeinsame Parameter
            'normalization': 0.9,
            'use_autocast': True,  # GPU-Optimierung

            # Demucs-spezifisch
            'demucs_shifts': 1,  # Weniger Shifts = schneller
            'demucs_overlap': 0.25,
            'demucs_segments_enabled': True,

            # VR/BS-RoFormer-spezifisch
            'vr_window_size': 1024,  # Größeres Fenster = schneller
            'vr_aggression': 5,
            'vr_enable_tta': False,
            'vr_enable_post_process': False,
        }
    },
    'balanced': {
        'name': 'Balanced',
        'description': 'Ausgewogen zwischen Qualität und Geschwindigkeit (empfohlen)',
        'params': {
            # Gemeinsame Parameter
            'normalization': 0.9,
            'use_autocast': True,

            # Demucs-spezifisch
            'demucs_shifts': 2,  # Standard
            'demucs_overlap': 0.25,
            'demucs_segments_enabled': True,

            # VR/BS-RoFormer-spezifisch
            'vr_window_size': 512,  # Standard
            'vr_aggression': 5,
            'vr_enable_tta': False,
            'vr_enable_post_process': False,
        }
    },
    'quality': {
        'name': 'Best Quality',
        'description': 'Beste Qualität, deutlich langsamer (2-3x länger)',
        'params': {
            # Gemeinsame Parameter
            'normalization': 0.9,
            'use_autocast': True,

            # Demucs-spezifisch
            'demucs_shifts': 5,  # Mehr Shifts = bessere Qualität
            'demucs_overlap': 0.5,  # Mehr Overlap = glattere Übergänge
            'demucs_segments_enabled': True,

            # VR/BS-RoFormer-spezifisch
            'vr_window_size': 320,  # Kleineres Fenster = bessere Qualität
            'vr_aggression': 5,
            'vr_enable_tta': True,  # Test-Time Augmentation
            'vr_enable_post_process': True,  # Artefakt-Entfernung
            'vr_post_process_threshold': 0.2,
        }
    },
    'ultra': {
        'name': 'Ultra Quality',
        'description': 'Maximal mögliche Qualität (4-5x länger, nur für kritische Anwendungen)',
        'params': {
            # Gemeinsame Parameter
            'normalization': 0.9,
            'use_autocast': True,

            # Demucs-spezifisch
            'demucs_shifts': 8,  # Maximum Shifts
            'demucs_overlap': 0.5,
            'demucs_segments_enabled': True,

            # VR/BS-RoFormer-spezifisch
            'vr_window_size': 320,
            'vr_aggression': 8,  # Höhere Aggression
            'vr_enable_tta': True,
            'vr_enable_post_process': True,
            'vr_post_process_threshold': 0.15,  # Sensibler
            'vr_high_end_process': 'mirroring',  # Hochfrequenz-Verarbeitung
        }
    }
}

# Default Quality Preset
DEFAULT_QUALITY_PRESET = 'balanced'

# GPU/CPU Konfiguration
USE_GPU = True  # Automatisch auf MPS (Apple Silicon) oder CUDA falls verfügbar
FALLBACK_TO_CPU = True

# Error Handling
MAX_RETRIES = 3
RETRY_STRATEGIES = [
    {'device': 'mps', 'chunk_length': CHUNK_LENGTH_SECONDS},
    {'device': 'cpu', 'chunk_length': CHUNK_LENGTH_SECONDS},
    {'device': 'cpu', 'chunk_length': MIN_CHUNK_LENGTH},
]

# Logging
LOG_FILE = LOGS_DIR / "app.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR

# Queue-Konfiguration
MAX_QUEUE_SIZE = 100
MAX_CONCURRENT_TASKS = 1  # Nur eine Datei gleichzeitig verarbeiten

# BlackHole-Konfiguration (macOS System Audio Recording)
BLACKHOLE_HOMEBREW_FORMULA = "blackhole-2ch"
BLACKHOLE_DEVICE_NAME = "BlackHole 2ch"

# UI-Konfiguration
DEFAULT_LANGUAGE = "de"  # de oder en
AVAILABLE_LANGUAGES = ["de", "en"]

# App-Metadaten
APP_NAME = "Stem Separator"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Your Name"

# File Size Limits (optional warnings)
WARN_FILE_SIZE_MB = 50  # Warnung bei großen Dateien
MAX_FILE_SIZE_MB = 500  # Harte Grenze (kann überschrieben werden)

# System Audio Recording
RECORDING_SAMPLE_RATE = 44100
RECORDING_CHANNELS = 2  # Stereo
RECORDING_FORMAT = 'float32'  # Internes Format
