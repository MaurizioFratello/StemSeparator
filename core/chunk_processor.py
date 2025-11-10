"""
Chunk Processor für das Zerlegen und Zusammenfügen von Audio-Dateien
"""
from pathlib import Path
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass
import numpy as np
import soundfile as sf

from config import (
    CHUNK_LENGTH_SECONDS,
    CHUNK_OVERLAP_SECONDS,
    MIN_CHUNK_LENGTH,
    TEMP_DIR
)
from utils.logger import get_logger
from utils.file_manager import get_file_manager


def _get_chunk_length_from_settings():
    """Hole chunk_length aus settings_manager falls verfügbar, sonst aus config"""
    try:
        from ui.settings_manager import get_settings_manager
        settings_mgr = get_settings_manager()
        return settings_mgr.get_chunk_length()
    except (ImportError, Exception):
        # Fallback auf config falls settings_manager nicht verfügbar
        return CHUNK_LENGTH_SECONDS

logger = get_logger()


@dataclass
class AudioChunk:
    """Represents a chunk of audio data"""
    index: int  # Chunk number (0-indexed)
    start_sample: int  # Start position in original audio
    end_sample: int  # End position in original audio
    audio_data: np.ndarray  # Audio samples (channels, samples)
    sample_rate: int
    has_overlap: bool = False


class ChunkProcessor:
    """Verarbeitet Audio-Chunks für große Dateien"""

    def __init__(
        self,
        chunk_length_seconds: int = CHUNK_LENGTH_SECONDS,
        overlap_seconds: int = CHUNK_OVERLAP_SECONDS
    ):
        self.chunk_length_seconds = chunk_length_seconds
        self.overlap_seconds = overlap_seconds
        self.logger = logger
        self.file_manager = get_file_manager()

        # Temp-Verzeichnis für Chunks
        self.chunks_dir = TEMP_DIR / "chunks"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

    def should_chunk(self, audio_file: Path) -> bool:
        """
        Entscheidet ob eine Audio-Datei gechunkt werden sollte

        Args:
            audio_file: Pfad zur Audio-Datei

        Returns:
            True wenn Datei gechunkt werden sollte
        """
        try:
            info = sf.info(str(audio_file))
            duration_seconds = info.duration

            # Hole aktuelle chunk_length aus Settings
            chunk_length = _get_chunk_length_from_settings()

            # Chunk wenn länger als chunk_length + overlap
            should_chunk = duration_seconds > (chunk_length + self.overlap_seconds)

            self.logger.debug(
                f"File duration: {duration_seconds:.1f}s, "
                f"Chunk threshold: {chunk_length + self.overlap_seconds}s, "
                f"Should chunk: {should_chunk}"
            )

            return should_chunk

        except Exception as e:
            self.logger.error(f"Error checking if file should be chunked: {e}")
            return False

    def chunk_audio(
        self,
        audio_file: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[AudioChunk]:
        """
        Zerlegt Audio-Datei in Chunks

        Args:
            audio_file: Pfad zur Audio-Datei
            progress_callback: Callback(current_chunk, total_chunks)

        Returns:
            Liste von AudioChunk Objekten
        """
        # Hole aktuelle chunk_length aus Settings
        chunk_length = _get_chunk_length_from_settings()

        self.logger.info(
            f"Chunking audio file: {audio_file.name} "
            f"(chunk_length: {chunk_length}s, overlap: {self.overlap_seconds}s)"
        )

        # Lade Audio-Datei
        audio_data, sample_rate = sf.read(str(audio_file), always_2d=True)

        # Transpose to (channels, samples)
        audio_data = audio_data.T

        total_samples = audio_data.shape[1]
        chunk_samples = int(chunk_length * sample_rate)
        overlap_samples = int(self.overlap_seconds * sample_rate)

        # Berechne Anzahl Chunks
        effective_chunk_size = chunk_samples - overlap_samples
        num_chunks = int(np.ceil(total_samples / effective_chunk_size))

        self.logger.info(
            f"File duration: {total_samples / sample_rate:.1f}s, "
            f"Chunk size: {self.chunk_length_seconds}s, "
            f"Creating {num_chunks} chunks"
        )

        chunks = []

        for i in range(num_chunks):
            # Berechne Start/End Samples für diesen Chunk
            start = i * effective_chunk_size
            end = min(start + chunk_samples, total_samples)

            # Extrahiere Chunk-Daten
            chunk_data = audio_data[:, start:end]

            chunk = AudioChunk(
                index=i,
                start_sample=start,
                end_sample=end,
                audio_data=chunk_data,
                sample_rate=sample_rate,
                has_overlap=(i > 0)  # Alle außer erstem Chunk haben Overlap
            )

            chunks.append(chunk)

            self.logger.debug(
                f"Chunk {i+1}/{num_chunks}: "
                f"samples {start}-{end} "
                f"({chunk_data.shape[1] / sample_rate:.1f}s)"
            )

            if progress_callback:
                progress_callback(i + 1, num_chunks)

        return chunks

    def merge_chunks(
        self,
        chunks: List[Tuple[AudioChunk, np.ndarray]],
        output_file: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> np.ndarray:
        """
        Fügt verarbeitete Chunks zusammen mit Crossfade im Overlap-Bereich

        Args:
            chunks: Liste von (original_chunk, processed_audio_data) Tuples
            output_file: Optionaler Pfad zum Speichern
            progress_callback: Callback(current_chunk, total_chunks)

        Returns:
            Zusammengefügtes Audio-Array (channels, samples)
        """
        if not chunks:
            raise ValueError("No chunks to merge")

        self.logger.info(f"Merging {len(chunks)} chunks")

        # Sortiere Chunks nach Index
        chunks = sorted(chunks, key=lambda x: x[0].index)

        first_chunk, first_data = chunks[0]
        sample_rate = first_chunk.sample_rate
        overlap_samples = int(self.overlap_seconds * sample_rate)

        # Berechne finale Länge
        # Jeder Chunk minus Overlap, außer der letzte behält seine volle Länge
        total_length = 0
        for i, (chunk, data) in enumerate(chunks):
            if i < len(chunks) - 1:
                # Nicht der letzte Chunk: subtrahiere Overlap
                total_length += data.shape[1] - overlap_samples
            else:
                # Letzter Chunk: volle Länge
                total_length += data.shape[1]

        # Initialisiere Output-Array
        num_channels = first_data.shape[0]
        merged_audio = np.zeros((num_channels, total_length), dtype=first_data.dtype)

        # Merge Chunks mit Crossfade
        current_pos = 0

        for i, (chunk, chunk_data) in enumerate(chunks):
            chunk_length = chunk_data.shape[1]

            if i == 0:
                # Erster Chunk: kopiere komplett
                merged_audio[:, :chunk_length] = chunk_data
                current_pos = chunk_length - overlap_samples

            else:
                # Crossfade im Overlap-Bereich
                # Linear fade: vorheriger Chunk fade-out, neuer Chunk fade-in

                # Overlap-Bereich
                overlap_data = chunk_data[:, :overlap_samples]

                # Erstelle Fade-Kurven
                fade_out = np.linspace(1.0, 0.0, overlap_samples)
                fade_in = np.linspace(0.0, 1.0, overlap_samples)

                # Apply Fades
                overlap_existing = merged_audio[:, current_pos:current_pos + overlap_samples]
                crossfaded = (overlap_existing * fade_out + overlap_data * fade_in)

                # Schreibe crossfaded Overlap
                merged_audio[:, current_pos:current_pos + overlap_samples] = crossfaded

                # Rest des Chunks (nach Overlap)
                rest_start = overlap_samples
                rest_length = chunk_length - overlap_samples
                merged_audio[:, current_pos + overlap_samples:current_pos + overlap_samples + rest_length] = \
                    chunk_data[:, rest_start:]

                current_pos += rest_length

            self.logger.debug(f"Merged chunk {i+1}/{len(chunks)}")

            if progress_callback:
                progress_callback(i + 1, len(chunks))

        # Speichere wenn output_file angegeben
        if output_file:
            # Transpose zurück zu (samples, channels) für soundfile
            audio_to_save = merged_audio.T
            sf.write(str(output_file), audio_to_save, sample_rate)
            self.logger.info(f"Merged audio saved to: {output_file}")

        return merged_audio

    def estimate_num_chunks(self, audio_file: Path) -> int:
        """
        Schätzt die Anzahl der Chunks die erstellt werden

        Args:
            audio_file: Pfad zur Audio-Datei

        Returns:
            Geschätzte Anzahl Chunks
        """
        try:
            info = sf.info(str(audio_file))
            duration_seconds = info.duration
            sample_rate = info.samplerate

            total_samples = int(duration_seconds * sample_rate)
            chunk_samples = int(self.chunk_length_seconds * sample_rate)
            overlap_samples = int(self.overlap_seconds * sample_rate)

            effective_chunk_size = chunk_samples - overlap_samples

            return int(np.ceil(total_samples / effective_chunk_size))

        except Exception as e:
            self.logger.error(f"Error estimating chunks: {e}")
            return 1

    def get_total_duration(self, chunks: List[AudioChunk]) -> float:
        """
        Berechnet Gesamt-Dauer aller Chunks (ohne Overlaps)

        Args:
            chunks: Liste von AudioChunk

        Returns:
            Duration in Sekunden
        """
        if not chunks:
            return 0.0

        # Summiere alle Chunks minus Overlaps
        total_samples = 0
        sample_rate = chunks[0].sample_rate

        for i, chunk in enumerate(chunks):
            if i < len(chunks) - 1:
                # Nicht letzter Chunk: subtrahiere Overlap
                overlap_samples = int(self.overlap_seconds * sample_rate)
                total_samples += chunk.audio_data.shape[1] - overlap_samples
            else:
                # Letzter Chunk: volle Länge
                total_samples += chunk.audio_data.shape[1]

        return total_samples / sample_rate

    def cleanup_chunk_files(self):
        """Löscht temporäre Chunk-Dateien"""
        try:
            import shutil
            if self.chunks_dir.exists():
                shutil.rmtree(self.chunks_dir)
                self.chunks_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug("Chunk files cleaned up")
        except Exception as e:
            self.logger.error(f"Error cleaning up chunk files: {e}")


# Globale Instanz
_chunk_processor: Optional[ChunkProcessor] = None


def get_chunk_processor() -> ChunkProcessor:
    """Gibt die globale ChunkProcessor-Instanz zurück"""
    global _chunk_processor
    if _chunk_processor is None:
        _chunk_processor = ChunkProcessor()
    return _chunk_processor


if __name__ == "__main__":
    # Test
    import tempfile

    # Erstelle Test-Audio (10 Sekunden)
    sample_rate = 44100
    duration = 10.0
    samples = int(sample_rate * duration)

    # Sinus-Ton
    t = np.linspace(0, duration, samples)
    audio_data = np.sin(2 * np.pi * 440 * t)
    stereo_data = np.column_stack([audio_data, audio_data])

    # Speichere als WAV
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        test_file = Path(f.name)
        sf.write(str(test_file), stereo_data, sample_rate)

    print(f"Created test file: {test_file}")

    # Test Chunk Processor
    cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

    print(f"Should chunk: {cp.should_chunk(test_file)}")
    print(f"Estimated chunks: {cp.estimate_num_chunks(test_file)}")

    chunks = cp.chunk_audio(test_file)
    print(f"Created {len(chunks)} chunks")

    for chunk in chunks:
        duration = chunk.audio_data.shape[1] / chunk.sample_rate
        print(f"  Chunk {chunk.index}: {duration:.2f}s, overlap={chunk.has_overlap}")

    # Cleanup
    test_file.unlink()
