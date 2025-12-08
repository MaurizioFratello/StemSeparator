"""
Separation Subprocess Worker

PURPOSE: Run audio separation in isolated subprocess to prevent resource leaks
CONTEXT: audio-separator library has multiprocessing semaphore leaks that cause
         segfaults on repeated use. Running each separation in a subprocess
         ensures OS cleans up all resources when subprocess exits.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Optional
import re


def run_separation_subprocess(
    audio_file: Path,
    model_id: str,
    output_dir: Path,
    model_filename: str,
    models_dir: Path,
    preset_params: dict,
    preset_attributes: dict,
    device: str = "cpu",
) -> Dict[str, Path]:
    """
    Run separation in subprocess - guaranteed clean resource management

    Args:
        audio_file: Path to audio file
        model_id: Model identifier
        output_dir: Output directory
        model_filename: Model filename to load
        models_dir: Directory containing models
        preset_params: Quality preset parameters
        preset_attributes: Quality preset attributes
        device: Device to use ('cpu', 'mps', 'cuda')

    Returns:
        Dict mapping stem names to output file paths
    """
    # Import here to keep subprocess isolated
    from audio_separator.separator import Separator as AudioSeparator
    from types import SimpleNamespace

    # Patch audio-separator version lookup to avoid None/AttributeError in frozen bundles
    if not hasattr(AudioSeparator, "_original_get_package_distribution"):
        AudioSeparator._original_get_package_distribution = (
            AudioSeparator.get_package_distribution
        )

        def _safe_get_package_distribution(self, package_name):
            try:
                dist = self._original_get_package_distribution(package_name)
                if dist is None or getattr(dist, "version", None) is None:
                    return SimpleNamespace(version="0.0.0-bundled")
                return dist
            except Exception:
                return SimpleNamespace(version="0.0.0-bundled")

        AudioSeparator.get_package_distribution = _safe_get_package_distribution

    def _apply_preset_attributes(separator: "AudioSeparator", attributes: dict):
        """
        Map preset attributes to the correct architecture-specific parameter buckets.

        WHY: audio-separator expects arch params inside separator.arch_specific_params,
        not as flat attributes. We still fall back to setattr for exotic values.
        """
        arch_mappings = {
            "demucs": (
                "Demucs",
                {
                    "segment_size": "segment_size",
                    "shifts": "shifts",
                    "overlap": "overlap",
                    "segments_enabled": "segments_enabled",
                },
            ),
            "vr": (
                "VR",
                {
                    "window_size": "window_size",
                    "aggression": "aggression",
                    "enable_tta": "enable_tta",
                    "enable_post_process": "enable_post_process",
                    "post_process_threshold": "post_process_threshold",
                    "high_end_process": "high_end_process",
                },
            ),
            "mdx": (
                "MDX",
                {
                    "segment_size": "segment_size",
                    "overlap": "overlap",
                    "batch_size": "batch_size",
                    "hop_length": "hop_length",
                    "enable_denoise": "enable_denoise",
                },
            ),
        }

        for attr_name, attr_value in attributes.items():
            handled = False

            for prefix, (arch_key, param_map) in arch_mappings.items():
                if attr_name.startswith(f"{prefix}_"):
                    target_key = attr_name[len(prefix) + 1 :]
                    mapped_key = param_map.get(target_key, target_key)
                    if (
                        hasattr(separator, "arch_specific_params")
                        and arch_key in separator.arch_specific_params
                    ):
                        separator.arch_specific_params[arch_key][
                            mapped_key
                        ] = attr_value
                        handled = True
                        break

            if not handled:
                setattr(separator, attr_name, attr_value)

    try:
        # Create separator instance
        separator = AudioSeparator(
            log_level=20,  # INFO
            model_file_dir=str(models_dir),
            output_dir=str(output_dir),
            **preset_params,
        )

        # Set architecture-specific attributes
        _apply_preset_attributes(separator, preset_attributes)

        # Load model
        separator.load_model(model_filename=model_filename)

        # Run separation
        output_files = separator.separate(str(audio_file))
    except Exception:
        import traceback

        traceback.print_exc(file=sys.stderr)
        raise

    # Parse output files
    stems = {}
    print(
        f"DEBUG: audio-separator returned {len(output_files) if output_files else 0} output files",
        file=sys.stderr,
    )
    if isinstance(output_files, list):
        for file_path in output_files:
            print(f"DEBUG: Processing output file: {file_path}", file=sys.stderr)
            file_path = Path(file_path)

            # Make absolute if needed
            if not file_path.is_absolute():
                file_path = output_dir / file_path

            # Extract stem name from filename
            # Format: filename_(stem).wav or filename_(stem)_modelname.wav
            # WHY: Use findall and get the LAST match, because input files might
            # contain parentheses in the filename (e.g., "Song(2025)_(Vocals).wav")
            matches = re.findall(r"\(([^)]+)\)", file_path.stem)

            # Known stem names to help identify the correct match
            known_stems = {
                "vocals",
                "vocal",
                "instrumental",
                "drums",
                "drum",
                "bass",
                "other",
                "piano",
                "guitar",
                "no_vocals",
                "no_other",
            }

            stem_name = None
            if matches:
                # Try to find a known stem name in the matches (prefer last occurrence)
                for match in reversed(matches):
                    if match.lower() in known_stems:
                        stem_name = match
                        break

                # If no known stem found, use the last parentheses content
                if stem_name is None:
                    stem_name = matches[-1]
            else:
                # Fallback: use last underscore-separated part
                stem_name = file_path.stem.split("_")[-1]

            stems[stem_name] = str(
                file_path
            )  # Convert to string for JSON serialization
            print(
                f"DEBUG: Extracted stem '{stem_name}' from {file_path.name}",
                file=sys.stderr,
            )

    print(f"DEBUG: Final stems dict: {list(stems.keys())}", file=sys.stderr)
    return stems


if __name__ == "__main__":
    # Read parameters from stdin as JSON
    params = json.loads(sys.stdin.read())

    # Convert string paths back to Path objects
    params["audio_file"] = Path(params["audio_file"])
    params["output_dir"] = Path(params["output_dir"])
    params["models_dir"] = Path(params["models_dir"])

    try:
        # Run separation
        stems = run_separation_subprocess(**params)

        # Write result to stdout as JSON
        result = {"success": True, "stems": stems, "error": None}
        print(json.dumps(result))
        sys.exit(0)

    except Exception as e:
        # Write error to stdout as JSON
        result = {"success": False, "stems": {}, "error": str(e)}
        print(json.dumps(result))
        sys.exit(1)
