"""
Zentrale Konfiguration für Stem Separator
"""

import os
import sys
from pathlib import Path


def get_base_dir():
    """
    Get the base directory for the application.

    When running from PyInstaller bundle, resources are in sys._MEIPASS.
    When running from source, resources are relative to this file.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Running in PyInstaller bundle
        return Path(sys._MEIPASS)
    else:
        # Running in normal Python environment
        return Path(__file__).parent


def get_user_dir():
    """
    Get the user data directory for writable files (logs, temp, etc.).

    In bundled app, we can't write to the app bundle, so use user's home directory.
    """
    if getattr(sys, "frozen", False):
        # Running in PyInstaller bundle - use user's Application Support
        if sys.platform == "darwin":  # macOS
            user_dir = Path.home() / "Library" / "Application Support" / "StemSeparator"
        elif sys.platform == "win32":  # Windows
            user_dir = Path(os.environ.get("APPDATA", Path.home())) / "StemSeparator"
        else:  # Linux
            user_dir = Path.home() / ".stemseparator"

        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    else:
        # Running from source - use project directory
        return Path(__file__).parent


# Basis-Pfade
BASE_DIR = get_base_dir()
USER_DIR = get_user_dir()

# Resources (read-only, bundled with app)
RESOURCES_DIR = BASE_DIR / "resources"
MODELS_DIR = RESOURCES_DIR / "models"
TRANSLATIONS_DIR = RESOURCES_DIR / "translations"
ICONS_DIR = RESOURCES_DIR / "icons"

# User data (writable, in user's home directory when bundled)
LOGS_DIR = USER_DIR / "logs"
TEMP_DIR = USER_DIR / "temp"

# Erstelle Verzeichnisse falls nicht vorhanden
for directory in [MODELS_DIR, LOGS_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Chunking-Konfiguration
CHUNK_LENGTH_SECONDS = 300  # 5 Minuten
CHUNK_OVERLAP_SECONDS = 2  # 2 Sekunden Overlap für nahtloses Merging
MIN_CHUNK_LENGTH = 150  # Minimale Chunk-Länge bei Fallback (2.5 min)

# Audio-Konfiguration
SUPPORTED_AUDIO_FORMATS = [".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac"]
DEFAULT_SAMPLE_RATE = 44100
EXPORT_SAMPLE_RATE = 44100
EXPORT_BIT_DEPTH = 16  # 16, 24, oder 32 bit

# Model-Konfiguration
# model_filename entspricht dem audio-separator Modell-Dateinamen
MODELS = {
    "mdx_vocals_hq": {
        "name": "MDX-Net Vocals",
        "stems": 2,
        "stem_names": ["Vocals", "Instrumental"],
        "size_mb": 110,
        "description": "⚡ Fast 2-stem separation - Perfect for karaoke",
        "model_filename": "UVR-MDX-NET-Voc_FT.onnx",
        "recommendation": "Fast vocal extraction, good for quick karaoke creation",
        "strength": "vocals",
        "backend": "mdx",
    },
    "mel-roformer": {
        "name": "Mel-Band RoFormer",
        "stems": 2,
        "stem_names": ["Vocals", "Instrumental"],
        "size_mb": 100,
        "description": "🎤 Best vocal quality - 2-stem separation",
        "model_filename": "model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt",
        "recommendation": "Highest quality vocals for professional vocal extraction",
        "strength": "vocals",  # Primary strength
    },
    "bs-roformer": {
        "name": "BS-RoFormer",
        "stems": 4,
        "stem_names": ["Vocals", "Drums", "Bass", "Other"],
        "size_mb": 300,
        "description": "🏆 Best overall quality - 4-stem balanced separation",
        "model_filename": "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
        "recommendation": "Highest quality 4-stem model, best balance across all stems",
        "strength": "balanced",  # Good for all stems
    },
    "demucs_4s": {
        "name": "Demucs v4 (4-stem)",
        "stems": 4,
        "stem_names": ["Vocals", "Drums", "Bass", "Other"],
        "size_mb": 160,
        "description": "⚡ Fast 4-stem separation - Great for drums",
        "model_filename": "htdemucs.yaml",
        "recommendation": "Fastest 4-stem option, excellent drum separation",
        "strength": "drums",  # Particularly good for drums
    },
    "demucs_6s": {
        "name": "Demucs v4 (6-stem)",
        "stems": 6,
        "stem_names": ["Vocals", "Drums", "Bass", "Piano", "Guitar", "Other"],
        "size_mb": 240,
        "description": "🎸 Maximum detail - Separates Piano & Guitar",
        "model_filename": "htdemucs_6s.yaml",
        "recommendation": "Only model with Piano/Guitar separation - for detailed work",
        "strength": "versatile",  # Most stems
    },
}

# Default Model
DEFAULT_MODEL = "demucs_6s"

# Quality Presets für Separation
# Diese beeinflussen die Qualität und Geschwindigkeit der Stem-Trennung
QUALITY_PRESETS = {
    "fast": {
        "name": "Fast",
        "description": "Schnellere Verarbeitung, geringere Qualität",
        "params": {},  # Keine zusätzlichen __init__ Parameter
        # Architektur-spezifische Parameter werden als Attribute gesetzt
        "attributes": {
            "demucs_shifts": 1,
            "demucs_overlap": 0.25,
            "vr_window_size": 1024,
            "vr_aggression": 5,
            "vr_enable_tta": False,
            "vr_enable_post_process": False,
            "mdx_segment_size": 256,
            "mdx_overlap": 0.22,
            "mdx_batch_size": 1,
            "mdx_hop_length": 1024,
            "mdx_enable_denoise": False,
        },
    },
    "balanced": {
        "name": "Balanced",
        "description": "Ausgewogen zwischen Qualität und Geschwindigkeit (empfohlen)",
        "params": {},
        "attributes": {
            "demucs_shifts": 2,
            "demucs_overlap": 0.25,
            "vr_window_size": 512,
            "vr_aggression": 5,
            "vr_enable_tta": False,
            "vr_enable_post_process": False,
            "mdx_segment_size": 256,
            "mdx_overlap": 0.28,
            "mdx_batch_size": 1,
            "mdx_hop_length": 1024,
            "mdx_enable_denoise": False,
        },
    },
    "quality": {
        "name": "Best Quality",
        "description": "Beste Qualität, deutlich langsamer (2-3x länger)",
        "params": {},
        "attributes": {
            "demucs_shifts": 5,
            "demucs_overlap": 0.5,
            "vr_window_size": 320,
            "vr_aggression": 5,
            "vr_enable_tta": True,
            "vr_enable_post_process": True,
            "vr_post_process_threshold": 0.2,
            "mdx_segment_size": 256,
            "mdx_overlap": 0.35,
            "mdx_batch_size": 1,
            "mdx_hop_length": 1024,
            "mdx_enable_denoise": True,
        },
    },
    "ultra": {
        "name": "Ultra Quality",
        "description": "Maximal mögliche Qualität (4-5x länger, nur für kritische Anwendungen)",
        "params": {},
        "attributes": {
            "demucs_shifts": 8,
            "demucs_overlap": 0.5,
            "vr_window_size": 320,
            "vr_aggression": 8,
            "vr_enable_tta": True,
            "vr_enable_post_process": True,
            "vr_post_process_threshold": 0.15,
            "vr_high_end_process": "mirroring",
            "mdx_segment_size": 384,
            "mdx_overlap": 0.45,
            "mdx_batch_size": 1,
            "mdx_hop_length": 1024,
            "mdx_enable_denoise": True,
        },
    },
}

# Default Quality Preset
DEFAULT_QUALITY_PRESET = "balanced"

# Ensemble-Konfiguration für Model-Kombinationen
# SIMPLIFIED: Only staged ensembles for best quality with clear progression
# WHY: Staged approach avoids interference, single models sufficient for speed
ENSEMBLE_CONFIGS = {
    # Staged ensembles: fuse vocals first, then process residual for drums/bass/other
    "balanced_staged": {
        "name": "Balanced",
        "description": "⚡ Recommended - Good quality, reasonable processing time (~2x)",
        "vocal_models": ["mel-roformer", "mdx_vocals_hq", "demucs_4s"],
        "residual_models": ["demucs_4s"],
        "fusion_strategy": "mask_blend",
        "fusion_stems": ["vocals"],
        "vocal_weights": {"vocals": [0.40, 0.40, 0.20]},
        "residual_weights": {"drums": [1.0], "bass": [1.0], "other": [1.0]},
        "mdx_params": {"segment_size": 256, "overlap": 0.28, "enable_denoise": False},
        "demucs_params": {"shifts": 2, "overlap": 0.25},
        "time_multiplier": 2.0,
        "quality_gain": "+0.5-0.7 dB SDR",
    },
    "quality_staged": {
        "name": "Quality",
        "description": "🏆 Professional quality - Best balance of quality/time (~2.5x)",
        "vocal_models": ["mel-roformer", "mdx_vocals_hq", "demucs_4s"],
        "residual_models": ["demucs_4s", "bs-roformer"],
        "fusion_strategy": "mask_blend",
        "fusion_stems": ["vocals"],
        "vocal_weights": {"vocals": [0.40, 0.40, 0.20]},
        "residual_weights": {
            "drums": [0.60, 0.40],
            "bass": [0.60, 0.40],
            "other": [0.55, 0.45],
        },
        "mdx_params": {"segment_size": 256, "overlap": 0.35, "enable_denoise": True},
        "demucs_params": {"shifts": 4, "overlap": 0.40},
        "time_multiplier": 2.5,
        "quality_gain": "+0.8 dB SDR",
    },
    "ultra_staged": {
        "name": "Ultra",
        "description": "💎 Maximum quality - For critical applications (~3.5x)",
        "vocal_models": ["mel-roformer", "mdx_vocals_hq", "demucs_4s"],
        "residual_models": ["demucs_4s", "bs-roformer"],
        "fusion_strategy": "mask_blend",
        "fusion_stems": ["vocals"],
        "vocal_weights": {"vocals": [0.35, 0.45, 0.20]},
        "residual_weights": {
            "drums": [0.60, 0.40],
            "bass": [0.60, 0.40],
            "other": [0.55, 0.45],
        },
        "mdx_params": {"segment_size": 384, "overlap": 0.45, "enable_denoise": True},
        "demucs_params": {"shifts": 6, "overlap": 0.50},
        "time_multiplier": 3.5,
        "quality_gain": "+1.0 dB SDR",
    },
}

# Default Ensemble Config
DEFAULT_ENSEMBLE_CONFIG = "balanced_staged"

# GPU/CPU Konfiguration
USE_GPU = True  # Automatisch auf MPS (Apple Silicon) oder CUDA falls verfügbar
FALLBACK_TO_CPU = True

# Error Handling
MAX_RETRIES = 3
RETRY_STRATEGIES = [
    {"device": "mps", "chunk_length": CHUNK_LENGTH_SECONDS},
    {"device": "cpu", "chunk_length": CHUNK_LENGTH_SECONDS},
    {"device": "cpu", "chunk_length": MIN_CHUNK_LENGTH},
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
RECORDING_FORMAT = "float32"  # Internes Format
