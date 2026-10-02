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
import logging
import shutil


def _require_ffmpeg(logger_sub) -> None:
    """
    Fail fast (and actionably) when FFmpeg cannot be executed.

    WHY: audio-separator validates FFmpeg by invoking the bare command
    `ffmpeg -version`; with the binary missing that surfaces as a raw
    FileNotFoundError repeated across the app's three retry attempts, hiding
    the actual remedy (vendored binaries never fetched) behind traceback
    noise. One clear error here tells the user exactly what to run.
    """
    exe_names = ("ffmpeg.exe", "ffmpeg") if sys.platform == "win32" else ("ffmpeg",)
    if any(shutil.which(name) for name in exe_names):
        return
    message = (
        "FFmpeg executable not found on PATH. From the project root run "
        "`python packaging/vendor/fetch_vendor.py --platform linux` "
        "(or --platform windows); installing FFmpeg system-wide also works."
    )
    logger_sub.error(message)
    raise FileNotFoundError(message)


VALID_DEVICES = ("cpu", "cuda", "mps")

# Parenthesised stem tags audio-separator writes into output names, e.g.
# `track_(Vocals)_htdemucs.wav`. Authority for what counts as a stem file in
# the leftover-file fallback search.
KNOWN_STEMS = {
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


def _available_onnx_providers() -> list:
    try:
        import onnxruntime as ort

        return list(ort.get_available_providers())
    except Exception as exc:  # pragma: no cover - onnxruntime optional per model
        logging.getLogger("StemSeparator.Subprocess").warning(
            f"Could not query ONNX Runtime providers: {exc}"
        )
        return []


def _enforce_device(separator, requested_device: str, logger_sub) -> str:
    """
    Force audio-separator onto the device chosen by the application.

    WHY: `audio_separator.Separator` picks its own device inside the
         constructor (`torch.cuda.is_available()` -> cuda, else MPS, else CPU)
         and exposes no parameter to override it. The parent process therefore
         used to *ask* for a device that the worker silently ignored, so a user
         selecting CUDA could quietly get CPU inference - and vice versa.
         Overriding the public attributes after construction and before
         `load_model()` is the only supported seam: the model instances read
         `torch_device`/`onnx_execution_provider` at load time.

    Args:
        separator: constructed `audio_separator.separator.Separator`
        requested_device: 'cpu' | 'cuda' | 'mps'
        logger_sub: subprocess logger

    Returns:
        The device actually in use.

    Raises:
        RuntimeError: when a GPU device was requested but is unusable, with an
            actionable message (never a silent CPU downgrade).
    """
    if requested_device not in VALID_DEVICES:
        raise ValueError(
            f"Invalid device '{requested_device}', expected one of {VALID_DEVICES}"
        )

    import torch

    if requested_device == "cuda" and not torch.cuda.is_available():
        build = getattr(torch.version, "cuda", None)
        if build is None:
            raise RuntimeError(
                "CUDA was requested but this PyTorch installation has no CUDA "
                f"build (torch {torch.__version__}). Install the CUDA wheel, e.g. "
                "`pip install torch==2.9.0 torchaudio==2.9.0 "
                "--index-url https://download.pytorch.org/whl/cu128` "
                "(see docs/PACKAGING.md)."
            )
        raise RuntimeError(
            "CUDA was requested but torch reports no usable NVIDIA device. "
            "Check `nvidia-smi` (driver installed / GPU not busy) and that the "
            f"torch CUDA build (cu{build}) is supported by your driver."
        )

    if requested_device == "mps":
        mps = getattr(torch.backends, "mps", None)
        if mps is None or not mps.is_available():
            raise RuntimeError(
                "MPS was requested but is unavailable (Apple Silicon GPU with "
                "Metal enabled is required)."
            )

    # The accelerator provider is decided explicitly, never by "whatever
    # survives filtering": a CPU-only onnxruntime would otherwise satisfy the
    # list silently and MDX-Net/ONNX models would run on the CPU while the UI
    # claims GPU inference (INF-03 forbids exactly this kind of silent loss).
    accelerator_provider = {
        "cpu": None,
        "cuda": "CUDAExecutionProvider",
        "mps": "CoreMLExecutionProvider",
    }[requested_device]
    available = _available_onnx_providers()

    separator.torch_device_cpu = torch.device("cpu")
    separator.torch_device = torch.device(requested_device)

    if accelerator_provider is None:
        providers = ["CPUExecutionProvider"]
    elif accelerator_provider in available:
        providers = [accelerator_provider, "CPUExecutionProvider"]
    else:
        providers = ["CPUExecutionProvider"]
        logger_sub.warning(
            f"ONNX models will run on CPU: {accelerator_provider} is not present "
            f"in this onnxruntime build (available: {available or 'none'}). "
            "Install `audio-separator[gpu]` (or `onnxruntime-gpu`) to accelerate "
            "ONNX architectures such as MDX-Net; torch models still use "
            f"{requested_device.upper()}."
        )

    separator.onnx_execution_provider = providers

    # Keep the MPS handle consistent: some architectures fall back to
    # `torch_device_mps` when it is set instead of consulting torch_device.
    if requested_device == "mps":
        separator.torch_device_mps = torch.device("mps")
    else:
        separator.torch_device_mps = torch.device("cpu")

    logger_sub.info(
        f"Device enforced: torch={separator.torch_device} onnx={providers}"
    )
    return requested_device


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

    # Add diagnostics for debugging packaged app issues
    import os
    import logging

    # Setup subprocess logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stderr
    )
    logger_sub = logging.getLogger("StemSeparator.Subprocess")

    # Log subprocess environment
    logger_sub.info(f"Subprocess working directory: {os.getcwd()}")
    logger_sub.info(f"Output directory (absolute): {Path(output_dir).absolute()}")
    logger_sub.info(f"Audio file (absolute): {Path(audio_file).absolute()}")
    logger_sub.info(f"Models directory: {Path(models_dir).absolute()}")
    logger_sub.info(f"Model ID: {model_id}, Model file: {model_filename}")

    # The parent (`core/separator.py::separate`) already gates on FFmpeg
    # before the retry chain; this is the last line of defence for direct
    # worker invocations and for PATH drift between gate and spawn.
    # audio-separator itself only probes FFmpeg via a bare `ffmpeg -version`.
    _require_ffmpeg(logger_sub)

    try:
        # Create separator instance
        separator = AudioSeparator(
            log_level=20,  # INFO
            model_file_dir=str(models_dir),
            output_dir=str(output_dir),
            **preset_params,
        )

        # Force the device the application selected (audio-separator would
        # otherwise keep whatever it auto-detected).
        _enforce_device(separator, device, logger_sub)

        # Set architecture-specific attributes
        _apply_preset_attributes(separator, preset_attributes)

        # Load model
        logger_sub.info(f"Loading model: {model_filename}")
        separator.load_model(model_filename=model_filename)

        # Run separation
        logger_sub.info(f"Starting separation for: {audio_file}")
        output_files = separator.separate(str(audio_file))

        # Log what audio-separator returned
        logger_sub.info(f"audio-separator returned: type={type(output_files)}, count={len(output_files) if isinstance(output_files, list) else 'N/A'}")
        if isinstance(output_files, list) and len(output_files) > 0:
            logger_sub.info(f"Output files: {output_files}")

    except Exception:
        import traceback

        traceback.print_exc(file=sys.stderr)
        raise

    # Validate output_files before processing
    stems = {}

    if output_files is None:
        logger_sub.error("audio-separator returned None - separation failed silently")
        # Search for files in current working directory
        cwd = Path.cwd()
        cwd_files = list(cwd.glob("*"))
        logger_sub.info(f"Files in subprocess cwd ({cwd}): {[f.name for f in cwd_files[:20]]}")

        # Search for potential output files in output_dir
        output_files_found = list(Path(output_dir).glob(f"{Path(audio_file).stem}*"))
        logger_sub.info(f"Files in output_dir matching pattern: {[f.name for f in output_files_found]}")

        raise ValueError("audio-separator returned None - no output files generated")

    if not isinstance(output_files, list):
        logger_sub.error(f"audio-separator returned unexpected type: {type(output_files)}")
        raise TypeError(f"Expected list from audio-separator, got {type(output_files)}")

    if len(output_files) == 0:
        # WHY: deliberately NO rescue search. The previous "empty list -> glob
        # the output dir" fallback laundered failed runs into phantom
        # successes twice: once by adopting the *input file* as a bogus stem
        # (which got the user's recording renamed), and again by adopting
        # stale-but-correctly-tagged outputs of an earlier run, masking a GPU
        # OOM and short-circuiting the CPU fallback chain. If audio-separator
        # returned nothing, this attempt failed: raise and let the parent's
        # retry chain pick the next strategy.
        logger_sub.error(
            "audio-separator returned an empty output list - separation failed "
            f"(audio: {audio_file}, model: {model_filename})"
        )
        raise ValueError("audio-separator produced no output files")
    if isinstance(output_files, list):
        for file_path in output_files:
            file_path = Path(file_path)

            # Make absolute if needed
            if not file_path.is_absolute():
                file_path = output_dir / file_path

            # Verify file actually exists
            if not file_path.exists():
                logger_sub.warning(f"Expected output file does not exist: {file_path}")
                # Try to find it in other locations
                filename = file_path.name
                for search_path, _ in search_locations:
                    potential_path = search_path / filename
                    if potential_path.exists():
                        logger_sub.info(f"Found file in alternate location: {potential_path}")
                        file_path = potential_path
                        break
                else:
                    logger_sub.error(f"Could not find output file anywhere: {filename}")
                    continue  # Skip this file

            logger_sub.info(f"Processing output file: {file_path}")

            # Extract stem name from filename
            # Format: filename_(stem).wav or filename_(stem)_modelname.wav
            # WHY: Use findall and get the LAST match, because input files might
            # contain parentheses in the filename (e.g., "Song(2025)_(Vocals).wav")
            matches = re.findall(r"\(([^)]+)\)", file_path.stem)

            # Known stem names come from the module-level KNOWN_STEMS.

            stem_name = None
            if matches:
                # Try to find a known stem name in the matches (prefer last occurrence)
                for match in reversed(matches):
                    if match.lower() in KNOWN_STEMS:
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

    # Final validation: ensure we got at least some stems
    if not stems or len(stems) == 0:
        logger_sub.error("No stems were created after processing output files")
        logger_sub.error(f"output_files was: {output_files}")
        logger_sub.error(f"Working directory: {os.getcwd()}")
        logger_sub.error(f"Output directory: {output_dir}")

        # One final search attempt
        all_wav_files = list(Path(output_dir).glob("*.wav"))
        logger_sub.error(f"All .wav files in output directory: {[f.name for f in all_wav_files]}")

        raise ValueError(
            "Separation completed but no valid stem files were found. "
            "This may indicate a path resolution issue or audio-separator failure."
        )

    logger_sub.info(f"Successfully processed {len(stems)} stems: {list(stems.keys())}")
    return stems


def _emit_result(result: Dict, result_file: Optional[Path]) -> None:
    """
    Deliver the worker result to the parent.

    WHY two channels: the file is authoritative because a `--noconsole` Windows
    build has no stdout at all (print() raises OSError/ValueError there), while
    stdout keeps the protocol working for dev runs and any caller that still
    parses the pipe.
    """
    if result_file is not None:
        try:
            result_file.parent.mkdir(parents=True, exist_ok=True)
            result_file.write_text(json.dumps(result), encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"Could not write result file {result_file}: {exc}\n")

    if sys.stdout is not None:
        try:
            print(json.dumps(result), flush=True)
        except (OSError, ValueError):  # windowed process without a console
            pass


def run_worker_from_argv(argv: Optional[list] = None) -> int:
    """
    Worker entry point for both launch modes.

    Reads the JSON request from `--params-file <path>` when given (the frozen
    app path, required on Windows where stdin is unavailable), otherwise from
    stdin. Returns the process exit code.
    """
    argv = list(sys.argv[1:] if argv is None else argv)

    params_file: Optional[Path] = None
    if "--params-file" in argv:
        index = argv.index("--params-file")
        if index + 1 >= len(argv):
            sys.stderr.write("--params-file requires a path argument\n")
            return 2
        params_file = Path(argv[index + 1])

    try:
        if params_file is not None:
            params = json.loads(params_file.read_text(encoding="utf-8"))
        else:
            if sys.stdin is None:
                sys.stderr.write("No stdin and no --params-file given\n")
                return 2
            params = json.loads(sys.stdin.read())
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"Could not read worker parameters: {exc}\n")
        return 2

    result_file_value = params.pop("result_file", None)
    result_file = Path(result_file_value) if result_file_value else None

    for key in ("audio_file", "output_dir", "models_dir"):
        if key in params:
            params[key] = Path(params[key])

    try:
        stems = run_separation_subprocess(**params)
        result = {"success": True, "stems": stems, "error": None}
        code = 0
    except Exception as e:
        import traceback

        if sys.stderr is not None:
            try:
                traceback.print_exc(file=sys.stderr)
            except (OSError, ValueError):
                pass
        result = {"success": False, "stems": {}, "error": str(e)}
        code = 1

    _emit_result(result, result_file)
    return code


if __name__ == "__main__":
    sys.exit(run_worker_from_argv())
