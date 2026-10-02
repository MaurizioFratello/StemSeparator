#!/usr/bin/env python3
"""
Download all AI models for bundling with StemSeparator

This script fetches every model listed in `config.MODELS` into the writable
model directory (`config.MODELS_DIR`, which is `resources/models/` when
running from source) so the packaged application ships them.

WHY: weights can already exist in one of the directories `config` advertises
via `MODEL_SEARCH_PATHS` (bundled app dir, user cache, or the
`~/.audio-separator/models` fallback audio-separator uses). Those copies are
discovered and reported with their origin, but a model that exists only
*outside* the bundle directory is still fetched: the packaged app must be
self-contained and must never write into the read-only bundle at runtime.
Reads therefore use the whole search path, writes use `config.MODELS_DIR`.

Usage:
    python packaging/download_models.py            # fetch what is missing
    python packaging/download_models.py --force    # re-fetch every model
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional


# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MODELS
from core.model_manager import (
    find_model_file,
    model_search_dirs,
    source_label_for,
    writable_models_dir,
)
from utils.logger import get_logger


logger = get_logger()


def _select_models(models: Dict[str, dict], ids: Optional[List[str]] = None):
    """
    Resolve which `config.MODELS` entries this run should handle.

    Unknown ids are listed and skipped instead of aborting the whole run.
    """
    if not ids:
        return dict(models)

    selected = {}
    unknown = []
    for model_id in ids:
        if model_id in models:
            selected[model_id] = models[model_id]
        else:
            unknown.append(model_id)

    if unknown:
        known = ", ".join(sorted(models))
        logger.error(f"Unknown model id(s): {', '.join(unknown)}. Known: {known}")

    return selected


def _model_state(model_file: str, target_dir: Path, search_dirs: List[Path]):
    """
    Locate one model file, distinguishing bundle-local from external copies.

    Returns:
        (path inside the writable model dir, path found elsewhere) - either can
        be None, both are `Path` objects pointing at a verified complete copy.
    """
    bundled = find_model_file(model_file, [target_dir])
    elsewhere = None
    for directory in search_dirs:
        if directory == target_dir:
            continue
        candidate = find_model_file(model_file, [directory])
        if candidate is not None:
            elsewhere = candidate
            break
    return bundled, elsewhere


def download_all_models(force: bool = False, model_ids: Optional[List[str]] = None):
    """
    Download the models defined in config.py into the writable model dir.

    Args:
        force: re-download models even when a valid copy already sits in the
            writable model dir (a stale/corrupt file is deleted first)
        model_ids: restrict the run to these `config.MODELS` keys; default is
            every configured model

    Exits with status 1 when a model is missing from the writable model dir
    after the run, so a build script can never package an incomplete app
    silently.
    """
    try:
        from audio_separator.separator import Separator
    except ImportError:
        logger.error(
            "audio-separator not installed. Run: pip install -r requirements.txt"
        )
        sys.exit(1)

    # WHY: downloads always target the writable directory. Omitting
    # `model_file_dir` would make audio-separator drop the weights into a temp
    # folder instead, leaving `resources/models` empty and the build broken;
    # the bundled dir can also be read-only in frozen builds.
    target_dir = writable_models_dir()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        logger.error(
            f"Model directory {target_dir} is not writable - cannot download "
            f"models: {error}"
        )
        sys.exit(1)

    search_dirs = model_search_dirs()
    selected = _select_models(MODELS, model_ids)
    if not selected:
        logger.error("No model selected - check the model ids you passed")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("StemSeparator Model Download Script")
    print("=" * 70)
    print(f"\nDownloading all models to: {target_dir}")
    print("\nExisting weights are discovered in:")
    for directory in search_dirs:
        print(f"  - {directory} ({source_label_for(directory)})")
    if force:
        print("\nForce mode: every selected model is re-downloaded")
    total_mb = sum(model_config["size_mb"] for model_config in selected.values())
    print(f"Total size: ~{total_mb}MB")

    print("\nThis may take several minutes depending on your internet connection...")
    print("=" * 70 + "\n")

    total_models = len(selected)
    successful = 0
    failed: List[str] = []

    for idx, (model_id, model_config) in enumerate(selected.items(), 1):
        model_name = model_config["name"]
        model_file = model_config["model_filename"]
        size_mb = model_config["size_mb"]

        print(f"\n[{idx}/{total_models}] Downloading: {model_name}")
        print(f"    File: {model_file}")
        print(f"    Size: ~{size_mb}MB")
        print("-" * 70)

        bundled, elsewhere = _model_state(model_file, target_dir, search_dirs)

        # Already bundled? Nothing to do (audio-separator would skip it too).
        if bundled is not None and not force:
            print(f"✓ Already present in the model dir: {bundled}")
            successful += 1
            continue

        if bundled is not None and force:
            try:
                bundled.unlink()
            except OSError as error:
                logger.warning(f"Could not remove {bundled} for re-download: {error}")
                failed.append(model_name)
                print(f"✗ Failed to re-download {model_name}")
                print(f"  Error: {str(error)[:100]}")
                continue

        # WHY: a copy in another search dir is reported, not silently reused -
        # the bundle has to carry its own copy, so the download still happens.
        if elsewhere is not None:
            print(
                f"    Found an existing copy outside the model dir "
                f"({source_label_for(elsewhere.parent)}): {elsewhere}"
            )
            print("    Fetching it again so the packaged app is self-contained")

        try:
            # Create separator instance with this model
            # audio-separator will download the model if not present
            separator = Separator(
                model_name=model_file,
                model_file_dir=str(target_dir),
                output_dir=str(target_dir.parent / "temp" / "separated"),
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

    # Verify every selected model is bundled *in the writable model dir*: a
    # file that only exists in another search dir is not part of the package.
    print("\nVerifying bundled files:")
    missing: List[str] = []
    for model_config in selected.values():
        model_file = model_config["model_filename"]
        bundled, elsewhere = _model_state(model_file, target_dir, search_dirs)
        if bundled is not None:
            size_mb = bundled.stat().st_size / (1024 * 1024)
            print(f"  ✓ {model_file} ({size_mb:.1f}MB)")
        elif elsewhere is not None:
            print(
                f"  ✗ {model_file} (only found in {elsewhere.parent} "
                f"[{source_label_for(elsewhere.parent)}] - NOT bundled)"
            )
            missing.append(model_file)
        else:
            print(f"  ✗ {model_file} (not found)")
            missing.append(model_file)

    # Summary
    print("\n" + "=" * 70)
    print("Download Summary")
    print("=" * 70)
    print(f"Successful: {successful}/{total_models}")

    if failed or missing:
        if failed:
            print(f"Failed: {len(failed)}")
            for model_name in failed:
                print(f"  - {model_name}")
        if missing:
            print(f"Not bundled: {len(missing)}")
            for model_file in missing:
                print(f"  - {model_file}")
        print(
            "\n⚠ Some models failed to download. You can try running this script again."
        )
        sys.exit(1)

    print("\n✓ All models downloaded successfully!")
    print(f"\nModels are ready for packaging in: {target_dir}")
    print("=" * 70 + "\n")


def main(argv: Optional[List[str]] = None):
    """
    CLI entry point.

    WHY: the historical invocation is `python packaging/download_models.py`
    without arguments and unrecognised arguments must therefore stay inert;
    only the additive `--force` switch and `--model` filter are interpreted.
    """
    arguments = list(sys.argv[1:] if argv is None else argv)

    # WHY an explicit help branch: the parser below is intentionally permissive
    # about stray arguments (the historical invocation passes none), which would
    # otherwise turn `--help` into a several-hundred-megabyte download.
    if any(argument in ("-h", "--help") for argument in arguments):
        print(__doc__.strip())
        print("Options:\n  -h, --help      show this message\n"
              "      --force, -f   re-download models that already exist\n"
              "      --model ID[,ID...]   limit to these model ids")
        return 0

    unknown_flags = [
        argument
        for argument in arguments
        if argument.startswith("--")
        and argument not in ("--force", "--help")
        and not argument.startswith("--model")
    ]
    if unknown_flags:
        logger.error(
            f"Unrecognised option(s): {', '.join(unknown_flags)} (try --help)"
        )
        return 2

    force = any(argument in ("--force", "-f") for argument in arguments)

    model_ids: Optional[List[str]] = None
    for index, argument in enumerate(arguments):
        if argument == "--model" and index + 1 < len(arguments):
            model_ids = arguments[index + 1].split(",")
        elif argument.startswith("--model="):
            model_ids = argument.split("=", 1)[1].split(",")

    download_all_models(force=force, model_ids=model_ids)
    return 0


if __name__ == "__main__":
    # WHY: `main()` returns the process exit code (2 for bad options, and
    # download failures exit inside `download_all_models`); dropping it would
    # make a broken build step look successful to CI.
    sys.exit(main())
