"""
Core Separator - Haupt-Logik für Audio Stem Separation
"""

from pathlib import Path
from typing import Optional, Dict, Callable, List
from dataclasses import dataclass
import time
import re
import threading
import gc
import subprocess
import json
import sys
import os
import uuid
import numpy as np
import soundfile as sf
import librosa

from config import (
    MODELS,
    DEFAULT_MODEL,
    DEFAULT_SAMPLE_RATE,
    TEMP_DIR,
    EXPORT_SAMPLE_RATE,
    EXPORT_BIT_DEPTH,
    QUALITY_PRESETS,
    DEFAULT_QUALITY_PRESET,
    get_default_output_dir,
    DEFAULT_SEPARATED_DIR,
)
from core.model_manager import get_model_manager
from core.device_manager import get_device_manager
from core.chunk_processor import get_chunk_processor
from utils.logger import get_logger
from utils.error_handler import error_handler, SeparationError
from utils.file_manager import get_file_manager
from utils.path_utils import resolve_output_path
from utils.platform_utils import (
    bundled_binary_dirs,
    is_frozen,
    is_macos,
    numba_cuda_safe_env,
    popen_kwargs,
    system_binary_dirs,
)

logger = get_logger()


@dataclass
class SeparationResult:
    """Ergebnis einer Stem-Separation"""

    success: bool
    input_file: Path
    output_dir: Path
    stems: Dict[str, Path]  # stem_name -> file_path
    model_used: str
    device_used: str
    duration_seconds: float
    error_message: Optional[str] = None


class Separator:
    """Hauptklasse für Audio Stem Separation"""

    def __init__(self):
        self.logger = logger
        self.model_manager = get_model_manager()
        self.device_manager = get_device_manager()
        self.chunk_processor = get_chunk_processor()
        self.file_manager = get_file_manager()

        # Output-Verzeichnis
        self.output_dir = TEMP_DIR / "separated"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info("Separator initialized")

    def separate(
        self,
        audio_file: Path,
        model_id: Optional[str] = None,
        output_dir: Optional[Path] = None,
        quality_preset: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> SeparationResult:
        """
        Führt Stem-Separation durch

        Args:
            audio_file: Pfad zur Audio-Datei
            model_id: Model zu verwenden (default: DEFAULT_MODEL)
            output_dir: Output-Verzeichnis (default: temp/separated)
            quality_preset: Quality-Preset ('fast', 'balanced', 'quality', 'ultra')
            progress_callback: Callback(message, progress_percent)

        Returns:
            SeparationResult
        """
        start_time = time.time()

        # Validiere Input
        is_valid, error = self.file_manager.validate_audio_file(audio_file)
        if not is_valid:
            return SeparationResult(
                success=False,
                input_file=audio_file,
                output_dir=output_dir or self.output_dir,
                stems={},
                model_used="",
                device_used="",
                duration_seconds=0,
                error_message=error,
            )

        # CRITICAL: Ensure input audio is at DEFAULT_SAMPLE_RATE (44100 Hz)
        # WHY: All models require 44100 Hz input to prevent timing drift and desynchronization
        #      Resampling input once is better than resampling output stems multiple times
        original_audio_file = audio_file
        try:
            # Check current sample rate
            info = sf.info(str(audio_file))
            current_sr = info.samplerate

            if current_sr != DEFAULT_SAMPLE_RATE:
                self.logger.info(
                    f"Input audio is {current_sr} Hz, resampling to {DEFAULT_SAMPLE_RATE} Hz "
                    f"(required for all separation models)"
                )

                # Load audio
                audio_data, _ = sf.read(
                    str(audio_file), always_2d=True, dtype="float32"
                )
                audio_data = audio_data.T  # (samples, channels) -> (channels, samples)

                # Resample each channel
                resampled_channels = []
                for channel in audio_data:
                    resampled = librosa.resample(
                        channel,
                        orig_sr=current_sr,
                        target_sr=DEFAULT_SAMPLE_RATE,
                        res_type="soxr_hq",  # High-quality resampling
                    )
                    resampled_channels.append(resampled)

                resampled_audio = np.array(resampled_channels)

                # Save resampled audio to temp file
                temp_resampled_file = (
                    TEMP_DIR / f"{audio_file.stem}_resampled_44100.wav"
                )
                TEMP_DIR.mkdir(parents=True, exist_ok=True)
                sf.write(
                    str(temp_resampled_file),
                    resampled_audio.T,  # (channels, samples) -> (samples, channels)
                    DEFAULT_SAMPLE_RATE,
                    subtype="PCM_16",
                )

                # Use resampled file for separation
                audio_file = temp_resampled_file
                self.logger.debug(f"Created resampled temp file: {temp_resampled_file}")

        except Exception as e:
            self.logger.warning(
                f"Could not check/resample input audio: {e}. Proceeding with original file."
            )
            audio_file = original_audio_file

        # Wähle Model
        model_id = model_id or DEFAULT_MODEL
        model_info = self.model_manager.get_model_info(model_id)

        # Wähle Quality Preset
        quality_preset = quality_preset or DEFAULT_QUALITY_PRESET
        if quality_preset not in QUALITY_PRESETS:
            self.logger.warning(
                f"Unknown quality preset '{quality_preset}', using 'balanced'"
            )
            quality_preset = "balanced"

        if not model_info:
            error_msg = f"Unknown model: {model_id}"
            self.logger.error(error_msg)
            return self._create_error_result(
                audio_file, output_dir, error_msg, time.time() - start_time
            )

        # Output-Verzeichnis
        # Resolve to absolute path and use default if None
        if output_dir is None:
            output_dir = get_default_output_dir("separated")
        else:
            # Resolve to absolute path and ensure directory exists
            output_dir = resolve_output_path(output_dir, DEFAULT_SEPARATED_DIR)
        
        self.logger.info(f"Output directory: {output_dir}")

        preset_info = QUALITY_PRESETS[quality_preset]
        self.logger.info(
            f"Starting separation: {audio_file.name} | "
            f"Model: {model_info.name} | "
            f"Quality: {preset_info['name']} | "
            f"Device: {self.device_manager.get_device()}"
        )

        if progress_callback:
            progress_callback(f"Preparing separation with {model_info.name}", 5)

        # Entscheide ob Chunking nötig ist
        needs_chunking = self.chunk_processor.should_chunk(audio_file)

        try:
            if needs_chunking:
                result = self._separate_with_chunking(
                    audio_file,
                    model_id,
                    model_info,
                    output_dir,
                    quality_preset,
                    progress_callback,
                )
            else:
                result = self._separate_single(
                    audio_file,
                    model_id,
                    model_info,
                    output_dir,
                    quality_preset,
                    progress_callback,
                )

            duration = time.time() - start_time
            result.duration_seconds = duration

            self.logger.info(
                f"Separation completed in {duration:.1f}s | "
                f"{len(result.stems)} stems created"
            )

            if progress_callback:
                progress_callback("Separation complete!", 100)

            return result

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Separation failed: {e}", exc_info=True)

            return self._create_error_result(
                audio_file, output_dir, str(e), duration, model_id
            )

    def _separate_single(
        self,
        audio_file: Path,
        model_id: str,
        model_info,
        output_dir: Path,
        quality_preset: str,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> SeparationResult:
        """Separiert Audio-Datei ohne Chunking"""

        if progress_callback:
            progress_callback("Loading model...", 10)

        # Nutze Error Handler mit Retry-Logik
        def separation_func(device="cpu", chunk_length=None):
            return self._run_separation(
                audio_file,
                model_id,
                output_dir,
                quality_preset,
                device=device,
                progress_callback=progress_callback,
            )

        stems = error_handler.retry_with_fallback(separation_func)

        # Rename files to unified naming scheme (stem name at end, no model suffix)
        # WHY: audio-separator generates names with model suffix, we want unified format
        renamed_stems = {}
        for stem_name, stem_path in stems.items():
            # Create unified filename: {audio_file.stem}_({stem_name}).wav
            new_path = output_dir / f"{audio_file.stem}_({stem_name}).wav"

            # Verify source file exists before attempting rename
            if not stem_path.exists():
                self.logger.error(f"Cannot rename: source file does not exist: {stem_path}")
                raise SeparationError(f"Expected stem file not found: {stem_path}")

            # Only rename if different
            if stem_path != new_path:
                if new_path.exists():
                    # Remove old file if exists (shouldn't happen, but be safe)
                    new_path.unlink()

                # Rename file
                stem_path.rename(new_path)
                self.logger.debug(f"Renamed {stem_path.name} -> {new_path.name}")

            renamed_stems[stem_name] = new_path

        return SeparationResult(
            success=True,
            input_file=audio_file,
            output_dir=output_dir,
            stems=renamed_stems,
            model_used=model_id,
            device_used=self.device_manager.get_device(),
            duration_seconds=0,  # Wird später gesetzt
        )

    def _separate_with_chunking(
        self,
        audio_file: Path,
        model_id: str,
        model_info,
        output_dir: Path,
        quality_preset: str,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> SeparationResult:
        """Separiert Audio-Datei mit Chunking"""

        self.logger.info("File requires chunking for processing")

        if progress_callback:
            progress_callback("Chunking audio file...", 10)

        # Erstelle Chunks
        chunks = self.chunk_processor.chunk_audio(
            audio_file,
            progress_callback=lambda curr, total: (
                progress_callback(
                    f"Creating chunk {curr}/{total}", 10 + int(10 * curr / total)
                )
                if progress_callback
                else None
            ),
        )

        self.logger.info(f"Created {len(chunks)} chunks")

        # Separiere jeden Chunk
        separated_chunks = {}  # stem_name -> list of chunk arrays

        for i, chunk in enumerate(chunks):
            chunk_progress_base = 20 + int(60 * i / len(chunks))

            if progress_callback:
                progress_callback(
                    f"Processing chunk {i+1}/{len(chunks)}", chunk_progress_base
                )

            self.logger.log_chunk_progress(i + 1, len(chunks), audio_file.name)

            # Speichere Chunk als temporäre Datei
            temp_chunk_file = self.chunk_processor.chunks_dir / f"chunk_{i}.wav"
            audio_data_transposed = (
                chunk.audio_data.T
            )  # (channels, samples) -> (samples, channels)
            sf.write(str(temp_chunk_file), audio_data_transposed, chunk.sample_rate)

            # Separiere Chunk mit Retry
            def chunk_sep_func(device="cpu", chunk_length=None):
                return self._run_separation(
                    temp_chunk_file,
                    model_id,
                    self.chunk_processor.chunks_dir,
                    quality_preset,
                    device=device,
                )

            chunk_stems = error_handler.retry_with_fallback(chunk_sep_func)

            # Lade separierte Stems zurück als Arrays
            for stem_name, stem_file in chunk_stems.items():
                stem_data, _ = sf.read(str(stem_file), always_2d=True)
                stem_data = stem_data.T  # (samples, channels) -> (channels, samples)

                if stem_name not in separated_chunks:
                    separated_chunks[stem_name] = []

                separated_chunks[stem_name].append((chunk, stem_data))

            # Cleanup temp chunk file
            temp_chunk_file.unlink()

        if progress_callback:
            progress_callback("Merging chunks...", 85)

        # Merge Chunks für jeden Stem
        final_stems = {}

        for stem_name, chunk_tuples in separated_chunks.items():
            self.logger.info(f"Merging {len(chunk_tuples)} chunks for {stem_name}")

            # Unified naming: stem name at the end, no model suffix
            # WHY: Consistent naming across ensemble and normal modes
            output_file = output_dir / f"{audio_file.stem}_({stem_name}).wav"

            merged_audio = self.chunk_processor.merge_chunks(
                chunk_tuples, output_file=output_file
            )

            final_stems[stem_name] = output_file

        if progress_callback:
            progress_callback("Finalizing...", 95)

        # Cleanup
        self.chunk_processor.cleanup_chunk_files()

        return SeparationResult(
            success=True,
            input_file=audio_file,
            output_dir=output_dir,
            stems=final_stems,
            model_used=model_id,
            device_used=self.device_manager.get_device(),
            duration_seconds=0,  # Wird später gesetzt
        )

    def _run_separation(
        self,
        audio_file: Path,
        model_id: str,
        output_dir: Path,
        quality_preset: str,
        device: str = "cpu",
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> Dict[str, Path]:
        """
        Führt die eigentliche Separation mit audio-separator aus

        IMPORTANT: Runs separation in isolated subprocess to prevent resource leaks.
        The audio-separator library has multiprocessing semaphore leaks that cause
        segfaults on repeated use. Running in subprocess ensures OS cleans up all
        resources when subprocess exits.

        Args:
            audio_file: Audio-Datei
            model_id: Model ID
            output_dir: Output-Verzeichnis
            quality_preset: Quality-Preset ID
            device: Device ('cpu', 'mps', 'cuda')
            progress_callback: Progress Callback

        Returns:
            Dict mit stem_name -> file_path

        Raises:
            SeparationError: Bei Fehlern
        """
        self.logger.info(
            f"Running separation on device: {device} with preset: {quality_preset}"
        )

        # Setze Device
        if not self.device_manager.set_device(device):
            raise SeparationError(f"Could not set device to {device}")

        if progress_callback:
            progress_callback(f"Separating with {model_id} on {device}", 50)

        # Setup simulated progress during separation
        stop_progress = threading.Event()
        current_progress = [50]  # Use list to allow modification in thread

        def simulate_progress():
            """Simulate gradual progress from 50% to 80% during separation"""
            while not stop_progress.is_set() and current_progress[0] < 80:
                time.sleep(0.5)  # Update every 0.5 seconds
                if not stop_progress.is_set():
                    current_progress[0] = min(80, current_progress[0] + 1)
                    if progress_callback:
                        progress_callback(
                            f"Processing audio with {model_id}", current_progress[0]
                        )

        # Start progress simulation thread
        progress_thread = None
        if progress_callback:
            progress_thread = threading.Thread(target=simulate_progress, daemon=True)
            progress_thread.start()

        # IPC files are created inside the try; keep the names bound so the
        # finally-block can always clean up.
        params_file: Optional[Path] = None
        result_file: Optional[Path] = None

        try:
            # Prepare parameters for subprocess
            model_filename = MODELS[model_id]["model_filename"]
            preset_config = QUALITY_PRESETS[quality_preset]
            preset_params = preset_config.get("params", {}).copy()
            preset_attributes = preset_config.get("attributes", {})

            # Build subprocess parameters
            subprocess_params = {
                "audio_file": str(audio_file),
                "model_id": model_id,
                "output_dir": str(output_dir),
                "model_filename": model_filename,
                "models_dir": str(self.model_manager.models_dir),
                "preset_params": preset_params,
                "preset_attributes": preset_attributes,
                "device": device,
            }

            self.logger.info(f"Launching separation subprocess for {model_id}")

            # Prepare environment for the isolated worker
            env = os.environ.copy()
            # torch ships its own OpenMP runtime; audio-separator's deps may
            # load a second one, which the runtimes refuse to coexist with.
            env["KMP_DUPLICATE_LIB_OK"] = "TRUE"

            # Make the bundled/system FFmpeg discoverable even when the app was
            # started with a minimal PATH (double-click on Windows, launchd on
            # macOS, systemd user session on Linux).
            tool_paths = [str(d) for d in bundled_binary_dirs() + system_binary_dirs()]
            env["PATH"] = os.pathsep.join(tool_paths + [env.get("PATH", "")])

            # numba initialising the CUDA driver before torch poisons the
            # spawned worker's CUDA context.
            for env_key, env_value in numba_cuda_safe_env().items():
                env.setdefault(env_key, env_value)

            # WHY: audio-separator re-detects the device inside the worker and
            # has no CPU override parameter; hiding the GPU from the driver is
            # the only way to honour an explicit CPU choice for both the torch
            # and the ONNX paths.
            if device == "cpu":
                env["CUDA_VISIBLE_DEVICES"] = ""
            env["STEMSEPARATOR_SUBPROCESS"] = "1"

            # Launch subprocess
            # Use a dedicated flag when frozen so the bundled binary runs the
            # worker path, otherwise fall back to running the module directly.
            #
            # Parameters/results travel through files, not stdin/stdout: a
            # `--noconsole` Windows build (what the app ships as) has no usable
            # stdin/stdout at all, so the JSON-over-pipes protocol only works in
            # dev runs. stdout is still parsed as a fallback.
            ipc_token = uuid.uuid4().hex
            params_file = TEMP_DIR / f"sep-params-{ipc_token}.json"
            result_file = TEMP_DIR / f"sep-result-{ipc_token}.json"
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            subprocess_params["result_file"] = str(result_file)
            params_file.write_text(json.dumps(subprocess_params), encoding="utf-8")

            # The worker is addressed by absolute script path, not `-m module`:
            # `cwd` is the output directory (see subprocess_kwargs below), so
            # `-m core.x` is only importable when the app happens to be started
            # from the repo root. core/separation_subprocess.py imports nothing
            # first-party at module scope, so direct execution is safe anywhere.
            worker_script = Path(__file__).resolve().parent / "separation_subprocess.py"
            cmd = (
                [sys.executable, "--separation-subprocess", "--params-file", str(params_file)]
                if is_frozen()
                else [
                    sys.executable,
                    str(worker_script),
                    "--params-file",
                    str(params_file),
                ]
            )

            # Keep the worker invisible: no console window on Windows, own
            # session on POSIX, no Dock entry for the frozen macOS app.
            subprocess_kwargs = {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "env": env,
                # CRITICAL FIX for packaged apps: run from the output directory
                # so audio-separator writes stems next to the target instead of
                # inside the bundle (sys._MEIPASS).
                "cwd": str(output_dir),
            }
            subprocess_kwargs.update(popen_kwargs())

            if is_frozen() and is_macos():
                env["LSUIElement"] = "1"

            self.logger.info(
                f"Subprocess working directory set to: {output_dir} (cwd-relative paths OK)"
            )

            process = subprocess.Popen(cmd, **subprocess_kwargs)

            # Send parameters via stdin
            params_json = json.dumps(subprocess_params)

            # Wait for subprocess with timeout to prevent indefinite hangs
            # Timeout: 2 hours (generous for long files on CPU, but prevents true hangs)
            try:
                stdout, stderr = process.communicate(input=params_json, timeout=7200)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                raise SeparationError(
                    "Separation subprocess timed out after 2 hours. "
                    "This may indicate a hang or an extremely large file. "
                    f"File: {audio_file}"
                )

            # Stop progress simulation
            stop_progress.set()
            if progress_thread:
                progress_thread.join(timeout=1.0)

            # Log stderr output for diagnostics (even on success, may contain warnings)
            if stderr and stderr.strip():
                self.logger.info(f"Subprocess stderr output:\n{stderr}")

            # Check return code
            if process.returncode != 0:
                error_msg = (
                    f"Subprocess failed with code {process.returncode}.\n"
                    f"stdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                )
                self.logger.error(error_msg)
                raise SeparationError(error_msg)

            # Parse the result.
            # WHY prefer the result file: the windowed Windows build cannot
            # write to stdout, so the file is the authoritative channel; the
            # stdout parse stays for dev runs and older callers. A worker may
            # emit several JSON objects (retries), so the successful one wins.
            result = None
            successful_results = []

            if result_file.is_file():
                try:
                    file_result = json.loads(result_file.read_text(encoding="utf-8"))
                    if isinstance(file_result, dict):
                        successful_results.append(file_result)
                        result = file_result
                        self.logger.info("Parsed separation result from result file")
                except (json.JSONDecodeError, OSError) as e:
                    self.logger.warning(
                        f"Result file unreadable ({e}); falling back to stdout"
                    )

            stdout = stdout or ""
            if not successful_results:
                try:
                    # Try parsing as a single JSON object first (most common case)
                    result = json.loads(stdout)
                    if result["success"]:
                        successful_results.append(result)
                except (json.JSONDecodeError, KeyError, TypeError):
                    # If single parse fails, try parsing line-by-line
                    for line in stdout.strip().split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            line_result = json.loads(line)
                            if line_result.get("success"):
                                successful_results.append(line_result)
                        except json.JSONDecodeError:
                            continue

            if successful_results:
                result = successful_results[0]
            elif result is None:
                error_msg = (
                    "Failed to parse any valid JSON from subprocess output.\n"
                    f"stdout: {stdout}\nstderr: {stderr}\n"
                    f"result file: {result_file} (exists: {result_file.is_file()})"
                )
                self.logger.error(error_msg)
                raise SeparationError(error_msg)

            # Check if result indicates failure
            if not result.get("success"):
                error_msg = f"Separation failed: {result.get('error', 'Unknown error')}"
                self.logger.error(error_msg)
                raise SeparationError(error_msg)

            if progress_callback:
                progress_callback("Finalizing separation", 85)

            # Convert string paths back to Path objects
            stems = {name: Path(path) for name, path in result["stems"].items()}

            # Validate that we got at least some stems
            if not stems or len(stems) == 0:
                error_msg = (
                    f"Separation subprocess completed but returned no stems. "
                    f"This may indicate a path resolution issue in the packaged app. "
                    f"Output directory: {output_dir}\n"
                    f"Subprocess stdout: {stdout}\n"
                    f"Subprocess stderr: {stderr}"
                )
                self.logger.error(error_msg)
                raise SeparationError(error_msg)

            self.logger.info(
                f"Subprocess separation complete: {len(stems)} stems created"
            )

            return stems

        except SeparationError:
            # Stop progress simulation on error
            stop_progress.set()
            if progress_thread:
                progress_thread.join(timeout=1.0)
            raise

        except Exception as e:
            # Stop progress simulation on error
            stop_progress.set()
            if progress_thread:
                progress_thread.join(timeout=1.0)

            error_msg = f"Separation failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise SeparationError(error_msg) from e

        finally:
            # Never leave worker request/response files behind in TEMP_DIR.
            for ipc_file in (params_file, result_file):
                if ipc_file is not None:
                    try:
                        ipc_file.unlink(missing_ok=True)
                    except OSError:
                        pass

    def _create_error_result(
        self,
        audio_file: Path,
        output_dir: Optional[Path],
        error_message: str,
        duration: float,
        model_id: str = "",
    ) -> SeparationResult:
        """Erstellt ein SeparationResult für Fehler"""
        return SeparationResult(
            success=False,
            input_file=audio_file,
            output_dir=output_dir or self.output_dir,
            stems={},
            model_used=model_id,
            device_used=self.device_manager.get_device(),
            duration_seconds=duration,
            error_message=error_message,
        )


# Globale Instanz
_separator: Optional[Separator] = None


def get_separator() -> Separator:
    """Gibt die globale Separator-Instanz zurück"""
    global _separator
    if _separator is None:
        _separator = Separator()
    return _separator


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python separator.py <audio_file>")
        sys.exit(1)

    audio_file = Path(sys.argv[1])

    if not audio_file.exists():
        print(f"File not found: {audio_file}")
        sys.exit(1)

    separator = Separator()

    def progress(message, percent):
        print(f"[{percent:3d}%] {message}")

    result = separator.separate(audio_file, progress_callback=progress)

    print("\n=== Separation Result ===")
    print(f"Success: {result.success}")
    print(f"Model: {result.model_used}")
    print(f"Device: {result.device_used}")
    print(f"Duration: {result.duration_seconds:.1f}s")

    if result.success:
        print(f"\nStems created ({len(result.stems)}):")
        for stem_name, stem_path in result.stems.items():
            print(f"  - {stem_name}: {stem_path}")
    else:
        print(f"\nError: {result.error_message}")
