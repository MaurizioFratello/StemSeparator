"""
Core Separator - Haupt-Logik für Audio Stem Separation
"""
from pathlib import Path
from typing import Optional, Dict, Callable, List
from dataclasses import dataclass
import time
import re
import numpy as np
import soundfile as sf

from config import (
    MODELS,
    DEFAULT_MODEL,
    TEMP_DIR,
    EXPORT_SAMPLE_RATE,
    EXPORT_BIT_DEPTH,
    QUALITY_PRESETS,
    DEFAULT_QUALITY_PRESET
)
from core.model_manager import get_model_manager
from core.device_manager import get_device_manager
from core.chunk_processor import get_chunk_processor
from utils.logger import get_logger
from utils.error_handler import error_handler, SeparationError
from utils.file_manager import get_file_manager

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
        progress_callback: Optional[Callable[[str, int], None]] = None
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
                error_message=error
            )

        # Wähle Model
        model_id = model_id or DEFAULT_MODEL
        model_info = self.model_manager.get_model_info(model_id)

        # Wähle Quality Preset
        quality_preset = quality_preset or DEFAULT_QUALITY_PRESET
        if quality_preset not in QUALITY_PRESETS:
            self.logger.warning(f"Unknown quality preset '{quality_preset}', using 'balanced'")
            quality_preset = 'balanced'

        if not model_info:
            error_msg = f"Unknown model: {model_id}"
            self.logger.error(error_msg)
            return self._create_error_result(
                audio_file, output_dir, error_msg, time.time() - start_time
            )

        # Output-Verzeichnis
        output_dir = output_dir or self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

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
                    progress_callback
                )
            else:
                result = self._separate_single(
                    audio_file,
                    model_id,
                    model_info,
                    output_dir,
                    quality_preset,
                    progress_callback
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
                audio_file,
                output_dir,
                str(e),
                duration,
                model_id
            )

    def _separate_single(
        self,
        audio_file: Path,
        model_id: str,
        model_info,
        output_dir: Path,
        quality_preset: str,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> SeparationResult:
        """Separiert Audio-Datei ohne Chunking"""

        if progress_callback:
            progress_callback("Loading model...", 10)

        # Nutze Error Handler mit Retry-Logik
        def separation_func(device='cpu', chunk_length=None):
            return self._run_separation(
                audio_file,
                model_id,
                output_dir,
                quality_preset,
                device=device,
                progress_callback=progress_callback
            )

        stems = error_handler.retry_with_fallback(separation_func)

        return SeparationResult(
            success=True,
            input_file=audio_file,
            output_dir=output_dir,
            stems=stems,
            model_used=model_id,
            device_used=self.device_manager.get_device(),
            duration_seconds=0  # Wird später gesetzt
        )

    def _separate_with_chunking(
        self,
        audio_file: Path,
        model_id: str,
        model_info,
        output_dir: Path,
        quality_preset: str,
        progress_callback: Optional[Callable[[str, int], None]] = None
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
                    f"Creating chunk {curr}/{total}",
                    10 + int(10 * curr / total)
                ) if progress_callback else None
            )
        )

        self.logger.info(f"Created {len(chunks)} chunks")

        # Separiere jeden Chunk
        separated_chunks = {}  # stem_name -> list of chunk arrays

        for i, chunk in enumerate(chunks):
            chunk_progress_base = 20 + int(60 * i / len(chunks))

            if progress_callback:
                progress_callback(
                    f"Processing chunk {i+1}/{len(chunks)}",
                    chunk_progress_base
                )

            self.logger.log_chunk_progress(i + 1, len(chunks), audio_file.name)

            # Speichere Chunk als temporäre Datei
            temp_chunk_file = self.chunk_processor.chunks_dir / f"chunk_{i}.wav"
            audio_data_transposed = chunk.audio_data.T  # (channels, samples) -> (samples, channels)
            sf.write(str(temp_chunk_file), audio_data_transposed, chunk.sample_rate)

            # Separiere Chunk mit Retry
            def chunk_sep_func(device='cpu', chunk_length=None):
                return self._run_separation(
                    temp_chunk_file,
                    model_id,
                    self.chunk_processor.chunks_dir,
                    quality_preset,
                    device=device
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

            output_file = output_dir / f"{audio_file.stem}_{stem_name}.wav"

            merged_audio = self.chunk_processor.merge_chunks(
                chunk_tuples,
                output_file=output_file
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
            duration_seconds=0  # Wird später gesetzt
        )

    def _run_separation(
        self,
        audio_file: Path,
        model_id: str,
        output_dir: Path,
        quality_preset: str,
        device: str = 'cpu',
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> Dict[str, Path]:
        """
        Führt die eigentliche Separation mit audio-separator aus

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
        self.logger.info(f"Running separation on device: {device} with preset: {quality_preset}")

        # Setze Device
        if not self.device_manager.set_device(device):
            raise SeparationError(f"Could not set device to {device}")

        if progress_callback:
            progress_callback(f"Separating with {model_id} on {device}", 50)

        try:
            # Import audio_separator
            from audio_separator.separator import Separator as AudioSeparator

            # Hole model filename
            model_filename = MODELS[model_id]['model_filename']

            # Hole Quality-Preset-Konfiguration
            preset_config = QUALITY_PRESETS[quality_preset]
            preset_params = preset_config.get('params', {}).copy()
            preset_attributes = preset_config.get('attributes', {})

            # Erstelle Separator-Instanz mit grundlegenden Parametern
            separator = AudioSeparator(
                log_level=20,  # INFO level
                model_file_dir=str(self.model_manager.models_dir),
                output_dir=str(output_dir),
                **preset_params  # Grundlegende Parameter
            )

            # Setze architektur-spezifische Attribute
            for attr_name, attr_value in preset_attributes.items():
                setattr(separator, attr_name, attr_value)
                self.logger.debug(f"Set separator.{attr_name} = {attr_value}")

            # Lade das Modell
            separator.load_model(model_filename=model_filename)

            self.logger.debug(f"AudioSeparator created with model: {model_filename}")

            # Führe Separation durch
            output_files = separator.separate(str(audio_file))

            self.logger.debug(f"Separation complete, output: {output_files}")

            # Parse Output-Files
            stems = {}

            if isinstance(output_files, list):
                for file_path in output_files:
                    file_path = Path(file_path)

                    # Wenn Pfad nicht absolut ist, ergänze mit output_dir
                    if not file_path.is_absolute():
                        file_path = output_dir / file_path

                    # Extrahiere Stem-Name aus Dateiname
                    # Format: filename_(stem).wav oder filename_(stem)_modelname.wav
                    # Stem-Name steht in Klammern, z.B. (Piano), (Vocals), etc.
                    match = re.search(r'\(([^)]+)\)', file_path.stem)
                    if match:
                        stem_name = match.group(1)
                    else:
                        # Fallback: letztes Element nach Underscore
                        stem_name = file_path.stem.split('_')[-1]

                    stems[stem_name] = file_path

                    self.logger.debug(f"Parsed stem: {stem_name} -> {file_path}")

            return stems

        except ImportError as e:
            error_msg = "audio-separator not installed"
            self.logger.error(error_msg)
            raise SeparationError(error_msg) from e

        except Exception as e:
            error_msg = f"Separation failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise SeparationError(error_msg) from e

    def _create_error_result(
        self,
        audio_file: Path,
        output_dir: Optional[Path],
        error_message: str,
        duration: float,
        model_id: str = ""
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
            error_message=error_message
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
