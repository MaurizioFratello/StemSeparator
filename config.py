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
        # Running in PyInstaller bundle - use user-writable app data locations
        if sys.platform == "darwin":  # macOS
            user_dir = Path.home() / "Library" / "Application Support" / "StemSeparator"
        elif sys.platform == "win32":  # Windows
            # Prefer LOCALAPPDATA for caches/logs/models in Windows packaged apps.
            local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            user_dir = Path(local_app_data or Path.home()) / "StemSeparator"
        else:  # Linux
            user_dir = Path.home() / ".stemseparator"

        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    else:
        # Running from source - use project directory
        return Path(__file__).parent


def get_default_output_dir(subdirectory: str = "separated") -> Path:
    """
    Get default output directory following macOS conventions.

    WHY: macOS apps typically save user files to ~/Music for audio files.
         This provides a consistent, user-friendly location for both
         packaged and development modes.

    Args:
        subdirectory: Subdirectory name (e.g., "separated", "loops", "recordings")

    Returns:
        Path to default output directory (e.g., ~/Music/StemSeparator/separated)
        Directory is created if it doesn't exist.
    """
    if sys.platform == "darwin":  # macOS
        # Use Music folder for audio files (macOS convention)
        music_folder = Path.home() / "Music"
        if music_folder.exists():
            output_dir = music_folder / "StemSeparator" / subdirectory
        else:
            # Fallback to Documents if Music doesn't exist
            output_dir = Path.home() / "Documents" / "StemSeparator" / subdirectory
    elif sys.platform == "win32":  # Windows
        # Use Music folder on Windows
        music_folder = Path.home() / "Music"
        if music_folder.exists():
            output_dir = music_folder / "StemSeparator" / subdirectory
        else:
            # Fallback to Documents
            output_dir = Path.home() / "Documents" / "StemSeparator" / subdirectory
    else:  # Linux and others
        # Use Documents as fallback
        output_dir = Path.home() / "Documents" / "StemSeparator" / subdirectory

    # Create directory structure if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


# Basis-Pfade
BASE_DIR = get_base_dir()
USER_DIR = get_user_dir()

# Resources (read-only, bundled with app)
RESOURCES_DIR = BASE_DIR / "resources"
# Models must be writable for first-run downloads (especially in frozen apps)
MODELS_DIR = USER_DIR / "models"
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

# CRITICAL: Universal sample rate for all separation models and processing
# WHY: Mel-RoFormer and BS-RoFormer require 44100 Hz (hardcoded in model architecture)
#      All models must process audio at this exact rate to prevent timing drift/desynchronization
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
    "bs-roformer": {
        "name": "BS-RoFormer",
        "stems": 2,
        "stem_names": ["Vocals", "Instrumental"],
        "size_mb": 300,
        "description": "🏆 Best vocal quality - 2-stem separation",
        "model_filename": "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
        "recommendation": "Highest quality 2-stem model (SDR 12.9) for professional vocal extraction",
        "strength": "vocals",  # Primary strength
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
        "vocal_models": ["bs-roformer", "mdx_vocals_hq", "demucs_4s"],
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
        "vocal_models": ["bs-roformer", "mdx_vocals_hq", "demucs_4s"],
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
        "vocal_models": ["bs-roformer", "mdx_vocals_hq", "demucs_4s"],
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
APP_VERSION = "1.0.3"
APP_AUTHOR = "StemSeparator"

# File Size Limits (optional warnings)
WARN_FILE_SIZE_MB = 50  # Warnung bei großen Dateien
MAX_FILE_SIZE_MB = 500  # Harte Grenze (kann überschrieben werden)

# System Audio Recording
RECORDING_SAMPLE_RATE = 44100
RECORDING_CHANNELS = 2  # Stereo
RECORDING_FORMAT = "float32"  # Internes Format

# Default Output Directories
# WHY: Provide consistent default locations for user files in ~/Music/StemSeparator/
#      Works for both packaged and development modes
DEFAULT_SEPARATED_DIR = get_default_output_dir("separated")
DEFAULT_LOOPS_DIR = get_default_output_dir("loops")
DEFAULT_RECORDINGS_DIR = get_default_output_dir("recordings")
