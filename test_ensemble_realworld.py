#!/usr/bin/env python3
"""
Real-World Ensemble Separation Test

Tests ensemble mode with ACTUAL audio files and ACTUAL models.
This is the final integration test before production use.

Prerequisites:
1. Download models: Run the app and download at least 2 models (e.g., BS-RoFormer + Demucs)
2. Provide test audio: Place an audio file (MP3, WAV, FLAC) in the project root

Usage:
    python test_ensemble_realworld.py <audio_file>
    python test_ensemble_realworld.py song.mp3 --config balanced
    python test_ensemble_realworld.py song.mp3 --config quality
    python test_ensemble_realworld.py song.mp3 --config vocals_focus
"""
import sys
from pathlib import Path
import argparse
import time

# Add project to path
sys.path.insert(0, '/home/user/StemSeparator')

from core.ensemble_separator import get_ensemble_separator
from config import ENSEMBLE_CONFIGS, MODELS


def check_models_available():
    """Check which models are downloaded"""
    print("\n" + "="*70)
    print("CHECKING MODEL AVAILABILITY")
    print("="*70)

    from core.model_manager import get_model_manager
    manager = get_model_manager()

    available_models = []
    for model_id in MODELS.keys():
        if manager.is_model_downloaded(model_id):
            available_models.append(model_id)
            print(f"  ✓ {model_id}: {MODELS[model_id]['name']}")
        else:
            print(f"  ✗ {model_id}: Not downloaded")

    if not available_models:
        print("\n⚠️  NO MODELS DOWNLOADED!")
        print("\nTo download models:")
        print("  1. Run the StemSeparator GUI application")
        print("  2. Go to Settings")
        print("  3. Download at least 2 models (e.g., bs-roformer + demucs_4s)")
        print("  4. Re-run this test")
        return []

    print(f"\n✓ Found {len(available_models)} downloaded models")
    return available_models


def check_ensemble_config_compatible(config_name, available_models):
    """Check if ensemble config can run with available models"""
    config = ENSEMBLE_CONFIGS[config_name]
    required_models = config['models']

    missing = [m for m in required_models if m not in available_models]

    if missing:
        print(f"\n⚠️  Ensemble config '{config_name}' requires missing models:")
        for model_id in missing:
            print(f"     - {model_id}: {MODELS[model_id]['name']}")
        return False

    print(f"\n✓ Ensemble config '{config_name}' is compatible!")
    print(f"  Models: {required_models}")
    print(f"  Expected quality gain: {config['quality_gain']}")
    return True


def run_ensemble_separation(audio_file: Path, config_name: str = 'balanced'):
    """Run actual ensemble separation"""
    print("\n" + "="*70)
    print(f"RUNNING ENSEMBLE SEPARATION: {config_name.upper()}")
    print("="*70)

    # Check models
    available_models = check_models_available()
    if not available_models:
        return False

    # Check config compatibility
    if not check_ensemble_config_compatible(config_name, available_models):
        print("\nTIP: Try a different ensemble config or download missing models")
        return False

    # Verify audio file exists
    if not audio_file.exists():
        print(f"\n❌ Audio file not found: {audio_file}")
        return False

    print(f"\n📁 Input: {audio_file.name}")
    print(f"   Size: {audio_file.stat().st_size / 1024:.1f} KB")

    # Get ensemble separator
    separator = get_ensemble_separator()

    # Progress callback
    def progress(msg, pct):
        bar_length = 40
        filled = int(bar_length * pct / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\r  [{bar}] {pct:3d}% - {msg}", end='', flush=True)

    # Run separation
    print("\n\n🚀 Starting ensemble separation...")
    print("This will take 2-3x longer than single model but produce higher quality.\n")

    start_time = time.time()

    try:
        result = separator.separate_ensemble(
            audio_file=audio_file,
            ensemble_config=config_name,
            progress_callback=progress
        )

        elapsed = time.time() - start_time

        print("\n")  # New line after progress bar

        if result.success:
            print("\n" + "="*70)
            print("✅ ENSEMBLE SEPARATION SUCCESSFUL!")
            print("="*70)

            print(f"\n⏱️  Time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
            print(f"📊 Model: {result.model_used}")
            print(f"💻 Device: {result.device_used}")
            print(f"\n📁 Output directory: {result.output_dir}")

            print(f"\n🎵 Separated stems:")
            for stem_name, stem_file in result.stems.items():
                size_kb = stem_file.stat().st_size / 1024
                print(f"   ✓ {stem_name:15s} → {stem_file.name} ({size_kb:.1f} KB)")

            print("\n📈 Quality Expectations:")
            config = ENSEMBLE_CONFIGS[config_name]
            print(f"   Expected quality gain: {config['quality_gain']}")
            print(f"   Processing time multiplier: {config['time_multiplier']}x")

            print("\n💡 Tip: Compare ensemble output with single-model output")
            print("   to verify quality improvement!")

            return True
        else:
            print("\n" + "="*70)
            print("❌ ENSEMBLE SEPARATION FAILED")
            print("="*70)
            print(f"\nError: {result.error_message}")
            return False

    except Exception as e:
        print("\n\n❌ EXCEPTION DURING SEPARATION")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def list_ensemble_configs():
    """List all available ensemble configurations"""
    print("\n" + "="*70)
    print("AVAILABLE ENSEMBLE CONFIGURATIONS")
    print("="*70)

    for config_name, config in ENSEMBLE_CONFIGS.items():
        print(f"\n📦 {config['name']} (--config {config_name})")
        print(f"   {config['description']}")
        print(f"   Models: {', '.join(config['models'])}")
        print(f"   Quality gain: {config['quality_gain']}")
        print(f"   Time: {config['time_multiplier']}x slower")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Test ensemble separation with real audio and models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_ensemble_realworld.py song.mp3
  python test_ensemble_realworld.py song.wav --config balanced
  python test_ensemble_realworld.py song.flac --config quality
  python test_ensemble_realworld.py --list-configs
        """
    )
    parser.add_argument(
        'audio_file',
        nargs='?',
        type=Path,
        help='Audio file to separate (MP3, WAV, FLAC, etc.)'
    )
    parser.add_argument(
        '--config',
        choices=list(ENSEMBLE_CONFIGS.keys()),
        default='balanced',
        help='Ensemble configuration (default: balanced)'
    )
    parser.add_argument(
        '--list-configs',
        action='store_true',
        help='List all available ensemble configurations'
    )

    args = parser.parse_args()

    print("="*70)
    print("REAL-WORLD ENSEMBLE SEPARATION TEST")
    print("="*70)

    if args.list_configs:
        list_ensemble_configs()
        return 0

    if not args.audio_file:
        print("\n❌ Error: Audio file required")
        parser.print_help()
        return 1

    success = run_ensemble_separation(args.audio_file, args.config)

    if success:
        print("\n✅ Test completed successfully!")
        return 0
    else:
        print("\n❌ Test failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())
