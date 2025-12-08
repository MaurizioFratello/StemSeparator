"""
Unit Tests für Chunk Processor
"""

import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
import tempfile
import shutil

from core.chunk_processor import ChunkProcessor, AudioChunk, get_chunk_processor


@pytest.fixture
def test_audio_file():
    """Erstellt temporäre Test-Audio-Datei (10 Sekunden)"""
    sample_rate = 44100
    duration = 10.0
    samples = int(sample_rate * duration)

    # Sinus-Ton
    t = np.linspace(0, duration, samples)
    audio_data = np.sin(2 * np.pi * 440 * t)
    stereo_data = np.column_stack([audio_data, audio_data])

    # Speichere als WAV
    temp_dir = Path(tempfile.mkdtemp())
    test_file = temp_dir / "test.wav"
    sf.write(str(test_file), stereo_data, sample_rate)

    yield test_file

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def short_audio_file():
    """Erstellt kurze Test-Audio-Datei (2 Sekunden)"""
    sample_rate = 44100
    duration = 2.0
    samples = int(sample_rate * duration)

    t = np.linspace(0, duration, samples)
    audio_data = np.sin(2 * np.pi * 440 * t)
    stereo_data = np.column_stack([audio_data, audio_data])

    temp_dir = Path(tempfile.mkdtemp())
    test_file = temp_dir / "short.wav"
    sf.write(str(test_file), stereo_data, sample_rate)

    yield test_file

    shutil.rmtree(temp_dir)


@pytest.mark.unit
class TestAudioChunk:
    """Tests für AudioChunk Dataclass"""

    def test_audio_chunk_creation(self):
        """Teste AudioChunk Erstellung"""
        audio_data = np.zeros((2, 44100))  # 1 second stereo

        chunk = AudioChunk(
            index=0,
            start_sample=0,
            end_sample=44100,
            audio_data=audio_data,
            sample_rate=44100,
            has_overlap=False,
        )

        assert chunk.index == 0
        assert chunk.start_sample == 0
        assert chunk.end_sample == 44100
        assert chunk.audio_data.shape == (2, 44100)
        assert chunk.sample_rate == 44100
        assert chunk.has_overlap is False


@pytest.mark.unit
class TestChunkProcessor:
    """Tests für Chunk Processor"""

    def test_initialization(self):
        """Teste ChunkProcessor Initialisierung"""
        cp = ChunkProcessor(chunk_length_seconds=300, overlap_seconds=2)

        assert cp.chunk_length_seconds == 300
        assert cp.overlap_seconds == 2
        assert cp.chunks_dir.exists()

    def test_should_chunk_long_file(self, test_audio_file):
        """Teste should_chunk() für lange Datei"""
        cp = ChunkProcessor(chunk_length_seconds=5, overlap_seconds=1)

        # 10 Sekunden File sollte gechunkt werden bei 5s chunks
        assert cp.should_chunk(test_audio_file) is True

    def test_should_chunk_short_file(self, short_audio_file):
        """Teste should_chunk() für kurze Datei"""
        cp = ChunkProcessor(chunk_length_seconds=5, overlap_seconds=1)

        # 2 Sekunden File sollte nicht gechunkt werden
        assert cp.should_chunk(short_audio_file) is False

    def test_chunk_audio_creates_chunks(self, test_audio_file):
        """Teste chunk_audio() erstellt Chunks"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        chunks = cp.chunk_audio(test_audio_file)

        assert len(chunks) > 1
        assert all(isinstance(c, AudioChunk) for c in chunks)

    def test_chunk_audio_correct_number(self, test_audio_file):
        """Teste chunk_audio() erstellt korrekte Anzahl Chunks"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        chunks = cp.chunk_audio(test_audio_file)

        # 10 Sekunden mit 4s Chunks und 1s Overlap
        # Effektive Chunk-Größe: 4 - 1 = 3s
        # Anzahl Chunks: ceil(10 / 3) = 4
        assert len(chunks) == 4

    def test_chunk_audio_first_chunk_no_overlap(self, test_audio_file):
        """Teste dass erster Chunk kein Overlap hat"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        chunks = cp.chunk_audio(test_audio_file)

        assert chunks[0].has_overlap is False
        assert all(c.has_overlap for c in chunks[1:])

    def test_chunk_audio_sequential_indices(self, test_audio_file):
        """Teste dass Chunks sequentielle Indices haben"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        chunks = cp.chunk_audio(test_audio_file)

        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_chunk_audio_progress_callback(self, test_audio_file):
        """Teste Progress Callback"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        progress_calls = []

        def callback(current, total):
            progress_calls.append((current, total))

        chunks = cp.chunk_audio(test_audio_file, progress_callback=callback)

        assert len(progress_calls) == len(chunks)
        assert (
            progress_calls[-1][0] == progress_calls[-1][1]
        )  # Last call: current == total

    def test_estimate_num_chunks(self, test_audio_file):
        """Teste estimate_num_chunks()"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        estimated = cp.estimate_num_chunks(test_audio_file)
        actual_chunks = cp.chunk_audio(test_audio_file)

        assert estimated == len(actual_chunks)

    def test_estimate_num_chunks_invalid_file(self):
        """Teste estimate_num_chunks() mit ungültiger Datei"""
        cp = ChunkProcessor()

        estimated = cp.estimate_num_chunks(Path("/nonexistent.wav"))
        assert estimated == 1  # Fallback

    def test_merge_chunks_recreates_audio(self, test_audio_file):
        """Teste dass merge_chunks() Audio korrekt zusammenfügt"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        # Lade Original
        original_audio, sample_rate = sf.read(str(test_audio_file), always_2d=True)
        original_audio = original_audio.T

        # Chunk und merge
        chunks = cp.chunk_audio(test_audio_file)

        # Erstelle Chunk-Tuples (chunk, processed_data)
        # Hier nehmen wir die Original-Daten als "processed"
        chunk_tuples = [(chunk, chunk.audio_data) for chunk in chunks]

        merged = cp.merge_chunks(chunk_tuples)

        # Merged sollte ungefähr gleich lang sein wie Original
        # (kann minimal unterschiedlich sein wegen Rounding)
        original_length = original_audio.shape[1]
        merged_length = merged.shape[1]

        assert (
            abs(original_length - merged_length) < sample_rate * 0.1
        )  # <0.1s Differenz

    def test_merge_chunks_with_output_file(self, test_audio_file):
        """Teste merge_chunks() mit Output-File"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        chunks = cp.chunk_audio(test_audio_file)
        chunk_tuples = [(chunk, chunk.audio_data) for chunk in chunks]

        output_file = test_audio_file.parent / "merged.wav"

        merged = cp.merge_chunks(chunk_tuples, output_file=output_file)

        assert output_file.exists()

        # Prüfe dass Output-File gleiche Länge hat wie merged array
        output_audio, _ = sf.read(str(output_file), always_2d=True)
        assert output_audio.shape[0] == merged.shape[1]

        # Cleanup
        output_file.unlink()

    def test_merge_chunks_progress_callback(self, test_audio_file):
        """Teste Progress Callback beim Merging"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        chunks = cp.chunk_audio(test_audio_file)
        chunk_tuples = [(chunk, chunk.audio_data) for chunk in chunks]

        progress_calls = []

        def callback(current, total):
            progress_calls.append((current, total))

        merged = cp.merge_chunks(chunk_tuples, progress_callback=callback)

        assert len(progress_calls) == len(chunks)

    def test_merge_chunks_empty_list(self):
        """Teste merge_chunks() mit leerer Liste"""
        cp = ChunkProcessor()

        with pytest.raises(ValueError, match="No chunks to merge"):
            cp.merge_chunks([])

    def test_merge_chunks_crossfade(self, test_audio_file):
        """Teste dass Crossfade funktioniert (keine Klicks)"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        chunks = cp.chunk_audio(test_audio_file)
        chunk_tuples = [(chunk, chunk.audio_data) for chunk in chunks]

        merged = cp.merge_chunks(chunk_tuples)

        # Check for discontinuities (would indicate clicks)
        # Calculate differences between adjacent samples
        diff = np.abs(np.diff(merged[0, :]))  # First channel

        # Max difference should be reasonable (no huge jumps)
        # Bei 440Hz Sinus ist max diff ca. 0.06
        assert np.max(diff) < 0.1

    def test_get_total_duration_empty(self):
        """Teste get_total_duration() mit leerer Liste"""
        cp = ChunkProcessor()

        duration = cp.get_total_duration([])
        assert duration == 0.0

    def test_get_total_duration(self, test_audio_file):
        """Teste get_total_duration()"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        chunks = cp.chunk_audio(test_audio_file)
        duration = cp.get_total_duration(chunks)

        # Sollte ungefähr 10 Sekunden sein (Original-Länge)
        assert 9.5 < duration < 10.5

    def test_cleanup_chunk_files(self):
        """Teste cleanup_chunk_files()"""
        cp = ChunkProcessor()

        # Erstelle Test-Datei im chunks_dir
        test_file = cp.chunks_dir / "test.txt"
        test_file.write_text("test")

        assert test_file.exists()

        cp.cleanup_chunk_files()

        # Verzeichnis sollte existieren aber leer sein
        assert cp.chunks_dir.exists()
        assert not test_file.exists()

    def test_singleton(self):
        """Teste get_chunk_processor Singleton"""
        cp1 = get_chunk_processor()
        cp2 = get_chunk_processor()

        assert cp1 is cp2
        assert isinstance(cp1, ChunkProcessor)

    def test_chunk_audio_maintains_channels(self, test_audio_file):
        """Teste dass Channels erhalten bleiben"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        chunks = cp.chunk_audio(test_audio_file)

        # Alle Chunks sollten 2 Channels haben (Stereo)
        assert all(chunk.audio_data.shape[0] == 2 for chunk in chunks)

    def test_chunk_audio_sample_rate_consistent(self, test_audio_file):
        """Teste dass Sample Rate konsistent ist"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        chunks = cp.chunk_audio(test_audio_file)

        # Alle Chunks sollten gleiche Sample Rate haben
        assert all(chunk.sample_rate == chunks[0].sample_rate for chunk in chunks)
        assert chunks[0].sample_rate == 44100

    def test_merge_chunks_unsorted(self, test_audio_file):
        """Teste dass merge_chunks() Chunks sortiert"""
        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        chunks = cp.chunk_audio(test_audio_file)

        # Mische Chunks durcheinander
        import random

        chunk_tuples = [(chunk, chunk.audio_data) for chunk in chunks]
        random.shuffle(chunk_tuples)

        # Merge sollte trotzdem funktionieren
        merged = cp.merge_chunks(chunk_tuples)

        assert merged.shape[1] > 0
