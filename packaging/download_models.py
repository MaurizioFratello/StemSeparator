#!/usr/bin/env python3
"""
Download all AI models for bundling with StemSeparator

This script downloads all 4 models (~800MB total) to resources/models/
Run this before building the packaged application.

Usage:
    python packaging/download_models.py
"""

import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MODELS, MODELS_DIR
from utils.logger import get_logger

logger = get_logger()


def download_all_models():
    """Download all models defined in config.py"""

    try:
        from audio_separator.separator import Separator
    except ImportError:
        logger.error(
            "audio-separator not installed. Run: pip install -r requirements.txt"
        )
        sys.exit(1)

    print("\n" + "=" * 70)
    print("StemSeparator Model Download Script")
    print("=" * 70)
    print(f"\nDownloading all models to: {MODELS_DIR}")
    print(f"Total size: ~800MB")
    print("\nThis may take several minutes depending on your internet connection...")
    print("=" * 70 + "\n")

    total_models = len(MODELS)
    successful = 0
    failed = []

    for idx, (model_id, model_config) in enumerate(MODELS.items(), 1):
        model_name = model_config["name"]
        model_file = model_config["model_filename"]
        size_mb = model_config["size_mb"]

        print(f"\n[{idx}/{total_models}] Downloading: {model_name}")
        print(f"    File: {model_file}")
        print(f"    Size: ~{size_mb}MB")
        print("-" * 70)

        try:
            # Create separator instance with this model
            # audio-separator will download the model if not present
            separator = Separator(
                model_name=model_file,
                output_dir=str(MODELS_DIR.parent / "temp" / "separated"),
                output_format="wav",
            )

            # Load the model (triggers download if needed)
            separator.load_model()

            print(f"✓ Successfully downloaded {model_name}")
            successful += 1

        except Exception as e:
            logger.error(f"Failed to download {model_name}: {e}")
            failed.append(model_name)
            print(f"✗ Failed to download {model_name}")
            print(f"  Error: {str(e)[:100]}")

    # Summary
    print("\n" + "=" * 70)
    print("Download Summary")
    print("=" * 70)
    print(f"Successful: {successful}/{total_models}")

    if failed:
        print(f"Failed: {len(failed)}")
        for model_name in failed:
            print(f"  - {model_name}")
        print(
            "\n⚠ Some models failed to download. You can try running this script again."
        )
        sys.exit(1)
    else:
        print("\n✓ All models downloaded successfully!")
        print(f"\nModels are ready for packaging in: {MODELS_DIR}")

        # Verify files
        print("\nVerifying downloaded files:")
        for model_id, model_config in MODELS.items():
            model_file = model_config["model_filename"]
            model_path = MODELS_DIR / model_file
            if model_path.exists():
                size_mb = model_path.stat().st_size / (1024 * 1024)
                print(f"  ✓ {model_file} ({size_mb:.1f}MB)")
            else:
                print(f"  ✗ {model_file} (not found)")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    download_all_models()
