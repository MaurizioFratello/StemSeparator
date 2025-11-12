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
    'mel-roformer': {
        'name': 'Mel-Band RoFormer',
        'stems': 4,
        'size_mb': 100,
        'description': '🎤 Best for vocals - Fast & specialized (SDR 13.0)',
        'model_filename': 'mel_band_roformer_vocals.ckpt',
        'recommendation': 'Perfect for karaoke & vocal extraction',
        'strength': 'vocals'  # Primary strength
    },
    'bs-roformer': {
        'name': 'BS-RoFormer',
        'stems': 4,
        'size_mb': 300,
        'description': '🏆 State-of-the-art quality - Balanced (SDR 12.98)',
        'model_filename': 'model_bs_roformer_ep_317_sdr_12.9755.ckpt',
        'recommendation': 'Best for professional work',
        'strength': 'balanced'  # Good for all stems
    },
    'demucs_6s': {
        'name': 'Demucs v4 (6-stem)',
        'stems': 6,
        'size_mb': 240,
        'description': '🎸 Most versatile - 6 stems (Vocals, Drums, Bass, Piano, Guitar, Other)',
        'model_filename': 'htdemucs_6s.yaml',
        'recommendation': 'Best for detailed separation',
        'strength': 'versatile'  # Most stems
    },
    'demucs_4s': {
        'name': 'Demucs v4 (4-stem)',
        'stems': 4,
        'size_mb': 160,
        'description': '⚡ Fast & high quality - Balanced (Vocals, Drums, Bass, Other)',
        'model_filename': 'htdemucs.yaml',
        'recommendation': 'Best for most users',
        'strength': 'drums'  # Particularly good for drums
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
        'params': {},  # Keine zusätzlichen __init__ Parameter
        # Architektur-spezifische Parameter werden als Attribute gesetzt
        'attributes': {
            'demucs_shifts': 1,
            'demucs_overlap': 0.25,
            'vr_window_size': 1024,
            'vr_aggression': 5,
            'vr_enable_tta': False,
            'vr_enable_post_process': False,
        }
    },
    'balanced': {
        'name': 'Balanced',
        'description': 'Ausgewogen zwischen Qualität und Geschwindigkeit (empfohlen)',
        'params': {},
        'attributes': {
            'demucs_shifts': 2,
            'demucs_overlap': 0.25,
            'vr_window_size': 512,
            'vr_aggression': 5,
            'vr_enable_tta': False,
            'vr_enable_post_process': False,
        }
    },
    'quality': {
        'name': 'Best Quality',
        'description': 'Beste Qualität, deutlich langsamer (2-3x länger)',
        'params': {},
        'attributes': {
            'demucs_shifts': 5,
            'demucs_overlap': 0.5,
            'vr_window_size': 320,
            'vr_aggression': 5,
            'vr_enable_tta': True,
            'vr_enable_post_process': True,
            'vr_post_process_threshold': 0.2,
        }
    },
    'ultra': {
        'name': 'Ultra Quality',
        'description': 'Maximal mögliche Qualität (4-5x länger, nur für kritische Anwendungen)',
        'params': {},
        'attributes': {
            'demucs_shifts': 8,
            'demucs_overlap': 0.5,
            'vr_window_size': 320,
            'vr_aggression': 8,
            'vr_enable_tta': True,
            'vr_enable_post_process': True,
            'vr_post_process_threshold': 0.15,
            'vr_high_end_process': 'mirroring',
        }
    }
}

# Default Quality Preset
DEFAULT_QUALITY_PRESET = 'balanced'

# Ensemble-Konfiguration für Model-Kombinationen
# Kombiniert mehrere Modelle für höchste Qualität
ENSEMBLE_CONFIGS = {
    'balanced': {
        'name': 'Balanced Ensemble',
        'description': '2 Models - Good quality, reasonable speed',
        'models': ['bs-roformer', 'demucs_4s'],
        'time_multiplier': 2.0,
        'quality_gain': '+0.5-0.7 dB SDR',
        # Stem-spezifische Gewichte: welches Modell ist für welchen Stem besser
        'weights': {
            'vocals': [0.6, 0.4],     # BS-RoFormer besser für Vocals
            'drums': [0.4, 0.6],      # Demucs besser für Drums
            'bass': [0.5, 0.5],       # Ausgeglichen
            'other': [0.5, 0.5],      # Ausgeglichen
            'instrumental': [0.45, 0.55]  # Für 2-stem Modelle
        }
    },
    'quality': {
        'name': 'Quality Ensemble',
        'description': '3 Models - Best quality, slower (Phase 2)',
        'models': ['mel-roformer', 'bs-roformer', 'demucs_4s'],
        'time_multiplier': 3.0,
        'quality_gain': '+0.8-1.0 dB SDR',
        'weights': {
            'vocals': [0.45, 0.35, 0.20],      # Mel-RoFormer beste für Vocals
            'drums': [0.15, 0.35, 0.50],       # Demucs beste für Drums
            'bass': [0.20, 0.40, 0.40],        # BS-RoFormer & Demucs
            'other': [0.25, 0.40, 0.35],       # BS-RoFormer leicht besser
            'instrumental': [0.40, 0.35, 0.25] # Ausgeglichener
        }
    },
    'vocals_focus': {
        'name': 'Vocals Focus Ensemble',
        'description': '2 Models specialized for vocals/karaoke',
        'models': ['mel-roformer', 'bs-roformer'],
        'time_multiplier': 2.0,
        'quality_gain': '+0.6-0.8 dB (vocals only)',
        'weights': {
            'vocals': [0.55, 0.45],            # Mel-RoFormer Schwerpunkt
            'instrumental': [0.45, 0.55],      # BS-RoFormer für Instrumental
            'drums': [0.45, 0.55],
            'bass': [0.40, 0.60],
            'other': [0.45, 0.55]
        }
    }
}

# Default Ensemble Config
DEFAULT_ENSEMBLE_CONFIG = 'balanced'

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
