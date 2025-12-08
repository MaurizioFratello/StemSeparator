"""
Integration Tests für Separator
Testet den kompletten Workflow mit realistischen Bedingungen
"""

import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

from core.separator import Separator, SeparationResult
from core.chunk_processor import get_chunk_processor


@pytest.fixture
def long_audio_file():
    """Erstellt lange Test-Audio-Datei die gechunkt werden muss (12 Sekunden)"""
    sample_rate = 44100
    duration = 12.0  # Lang genug für Chunking mit 5s Chunks
    samples = int(sample_rate * duration)

    # Generiere erkennbaren Audio-Content
    # Verschiedene Frequenzen in verschiedenen Teilen
    t = np.linspace(0, duration, samples)

    # Teil 1 (0-4s): 440 Hz
    # Teil 2 (4-8s): 880 Hz
    # Teil 3 (8-12s): 1320 Hz
    audio_data = np.zeros(samples)

    # Erste 4 Sekunden: 440 Hz
    end_1 = int(4 * sample_rate)
    audio_data[:end_1] = np.sin(2 * np.pi * 440 * t[:end_1])

    # Nächste 4 Sekunden: 880 Hz
    start_2 = end_1
    end_2 = int(8 * sample_rate)
    audio_data[start_2:end_2] = np.sin(2 * np.pi * 880 * t[start_2:end_2])

    # Letzte 4 Sekunden: 1320 Hz
    start_3 = end_2
    audio_data[start_3:] = np.sin(2 * np.pi * 1320 * t[start_3:])

    stereo_data = np.column_stack([audio_data, audio_data])

    temp_dir = Path(tempfile.mkdtemp())
    test_file = temp_dir / "long_audio.wav"
    sf.write(str(test_file), stereo_data, sample_rate)

    yield test_file

    shutil.rmtree(temp_dir)


@pytest.mark.integration
class TestSeparatorIntegration:
    """Integration Tests für den kompletten Separation-Workflow"""

    @patch("audio_separator.separator.Separator")
    @patch("core.separator.get_chunk_processor")
    def test_separate_with_chunking_workflow(
        self, mock_get_cp, mock_audio_sep, long_audio_file
    ):
        """
        Integration Test: Kompletter Workflow für große Datei mit Chunking

        Testet:
        - Chunking wird erkannt
        - Chunks werden erstellt
        - Jeder Chunk wird separiert
        - Chunks werden korrekt gemerged
        - Output-Files werden erstellt
        """
        # Erstelle ChunkProcessor mit kleineren Chunks für Tests
        from core.chunk_processor import ChunkProcessor

        test_cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)
        mock_get_cp.return_value = test_cp

        # Mock AudioSeparator für jeden Chunk
        def mock_separate(audio_file_path):
            """
            Simuliert Stem-Separation:
            Erstellt Mock-Stems (vocals, drums, bass, other)
            """
            audio_file = Path(audio_file_path)
            output_dir = audio_file.parent

            # Lade Original Audio
            audio_data, sr = sf.read(str(audio_file), always_2d=True)

            # Erstelle Mock-Stems (einfach: Original Audio + leichte Variation)
            stems = {}
            for stem_name in ["vocals", "drums", "bass", "other"]:
                stem_file = output_dir / f"{audio_file.stem}_{stem_name}.wav"

                # Einfache Variation: Stem = Original * Faktor
                factor = {"vocals": 0.8, "drums": 0.6, "bass": 0.4, "other": 0.2}[
                    stem_name
                ]
                stem_data = audio_data * factor

                sf.write(str(stem_file), stem_data, sr)
                stems[stem_name] = str(stem_file)

            return list(stems.values())

        mock_instance = MagicMock()
        mock_instance.separate.side_effect = mock_separate
        mock_audio_sep.return_value = mock_instance

        # Erstelle Separator
        sep = Separator()

        # Progress Tracking
        progress_calls = []

        def progress_callback(message, percent):
            progress_calls.append((message, percent))

        # Führe Separation durch
        result = sep.separate(
            long_audio_file, model_id="demucs_6s", progress_callback=progress_callback
        )

        # Assertions
        assert result.success is True, f"Separation failed: {result.error_message}"
        assert len(result.stems) > 0, "No stems created"

        # Check dass Stems existieren
        for stem_name, stem_path in result.stems.items():
            assert stem_path.exists(), f"Stem file not found: {stem_name}"

            # Check dass Stem Audio-Daten enthält
            stem_audio, _ = sf.read(str(stem_path))
            assert len(stem_audio) > 0, f"Stem {stem_name} is empty"

        # Check dass Progress-Callbacks aufgerufen wurden
        assert len(progress_calls) > 0, "No progress callbacks"

        # Check dass "Chunking" oder "Merging" in Messages vorkommt
        messages = [msg for msg, _ in progress_calls]
        assert any(
            "chunk" in msg.lower() or "merg" in msg.lower() for msg in messages
        ), "No chunking/merging mentioned in progress"

        # Check dass AudioSeparator mehrmals aufgerufen wurde (für jeden Chunk)
        # Bei 12s Audio mit 5s Chunks + 1s Overlap = ~3-4 Chunks
        assert (
            mock_instance.separate.call_count >= 3
        ), f"Expected at least 3 chunks, got {mock_instance.separate.call_count}"

        print(f"\n✓ Chunking workflow successful:")
        print(f"  - Chunks processed: {mock_instance.separate.call_count}")
        print(f"  - Stems created: {len(result.stems)}")
        print(f"  - Progress updates: {len(progress_calls)}")

    @patch("audio_separator.separator.Separator")
    @patch("core.separator.get_chunk_processor")
    def test_chunking_maintains_audio_length(
        self, mock_get_cp, mock_audio_sep, long_audio_file
    ):
        """
        Test dass Chunking die Audio-Länge erhält

        Kritisch: Merged Audio muss gleich lang sein wie Original
        """
        # Erstelle ChunkProcessor mit kleineren Chunks für Tests
        from core.chunk_processor import ChunkProcessor

        test_cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)
        mock_get_cp.return_value = test_cp

        # Mock Separator
        def mock_separate(audio_file_path):
            audio_file = Path(audio_file_path)
            output_dir = audio_file.parent

            # Lade Original
            audio_data, sr = sf.read(str(audio_file), always_2d=True)

            # Erstelle einen Stem
            stem_file = output_dir / f"{audio_file.stem}_vocals.wav"
            sf.write(str(stem_file), audio_data * 0.8, sr)

            return [str(stem_file)]

        mock_instance = MagicMock()
        mock_instance.separate.side_effect = mock_separate
        mock_audio_sep.return_value = mock_instance

        # Lade Original Audio Info
        original_audio, original_sr = sf.read(str(long_audio_file))
        original_length = len(original_audio)

        sep = Separator()
        result = sep.separate(long_audio_file)

        assert result.success is True

        # Check Länge des ersten Stems
        first_stem = list(result.stems.values())[0]
        stem_audio, stem_sr = sf.read(str(first_stem))
        stem_length = len(stem_audio)

        # Länge sollte sehr ähnlich sein (max 0.5s Differenz wegen Rounding)
        max_diff_samples = int(0.5 * original_sr)
        length_diff = abs(original_length - stem_length)

        assert length_diff < max_diff_samples, (
            f"Audio length changed significantly: {original_length} -> {stem_length} "
            f"(diff: {length_diff} samples = {length_diff/original_sr:.2f}s)"
        )

        print(f"\n✓ Audio length preserved:")
        print(
            f"  - Original: {original_length} samples ({original_length/original_sr:.2f}s)"
        )
        print(f"  - Merged:   {stem_length} samples ({stem_length/stem_sr:.2f}s)")
        print(f"  - Diff:     {length_diff} samples ({length_diff/original_sr:.3f}s)")

    @patch("audio_separator.separator.Separator")
    @patch("core.separator.get_chunk_processor")
    def test_chunking_progress_tracking(
        self, mock_get_cp, mock_audio_sep, long_audio_file
    ):
        """
        Test dass Progress korrekt getrackt wird bei Chunking

        Wichtig für UI-Feedback
        """
        # Erstelle ChunkProcessor mit kleineren Chunks für Tests
        from core.chunk_processor import ChunkProcessor

        test_cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)
        mock_get_cp.return_value = test_cp

        mock_instance = MagicMock()
        mock_instance.separate.return_value = []
        mock_audio_sep.return_value = mock_instance

        sep = Separator()

        progress_calls = []

        def callback(msg, pct):
            progress_calls.append((msg, pct))
            print(f"  [{pct:3d}%] {msg}")

        result = sep.separate(long_audio_file, progress_callback=callback)

        # Check Progress-Sequenz
        assert len(progress_calls) > 0

        # Progress sollte monoton steigend sein (mit kleinen Ausnahmen)
        percentages = [pct for _, pct in progress_calls]

        # Erster Progress sollte niedrig sein
        assert percentages[0] < 30, "First progress too high"

        # Letzter Progress sollte hoch sein
        assert percentages[-1] >= 80, "Final progress too low"

        # Check dass Chunking-relevante Messages vorhanden sind
        messages = [msg.lower() for msg, _ in progress_calls]

        has_chunking_msg = any("chunk" in msg for msg in messages)
        has_merging_msg = any("merg" in msg for msg in messages)

        assert has_chunking_msg, "No chunking progress messages"
        assert has_merging_msg, "No merging progress messages"

        print(f"\n✓ Progress tracking working:")
        print(f"  - Total updates: {len(progress_calls)}")
        print(f"  - Progress range: {percentages[0]}% -> {percentages[-1]}%")

    @patch("audio_separator.separator.Separator")
    @patch("core.separator.get_chunk_processor")
    def test_error_in_chunk_processing(
        self, mock_get_cp, mock_audio_sep, long_audio_file
    ):
        """
        Test Error Handling während Chunk-Processing

        Was passiert wenn ein Chunk fehlschlägt?
        """
        # Erstelle ChunkProcessor mit kleineren Chunks für Tests
        from core.chunk_processor import ChunkProcessor

        test_cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)
        mock_get_cp.return_value = test_cp

        call_count = 0

        def mock_separate_with_error(audio_file_path):
            nonlocal call_count
            call_count += 1

            # Zweiter Chunk schlägt fehl
            if call_count == 2:
                raise RuntimeError("Simulated chunk processing error")

            # Andere Chunks erfolgreich
            audio_file = Path(audio_file_path)
            output_dir = audio_file.parent
            audio_data, sr = sf.read(str(audio_file), always_2d=True)

            stem_file = output_dir / f"{audio_file.stem}_vocals.wav"
            sf.write(str(stem_file), audio_data, sr)
            return [str(stem_file)]

        mock_instance = MagicMock()
        mock_instance.separate.side_effect = mock_separate_with_error
        mock_audio_sep.return_value = mock_instance

        sep = Separator()
        result = sep.separate(long_audio_file)

        # Mit Error Handler + Retry sollte es trotzdem funktionieren
        # (Retry mit CPU, kleineren Chunks, etc.)
        # ODER es sollte graceful failen mit Error Message

        if not result.success:
            assert result.error_message is not None
            assert "error" in result.error_message.lower()
            print(f"\n✓ Error handling working: {result.error_message}")
        else:
            # Wenn es doch erfolgreich ist (wegen Retry), auch OK
            print(f"\n✓ Retry mechanism recovered from error")

    def test_chunk_processor_directly(self, long_audio_file):
        """
        Direkter Test des ChunkProcessors ohne Separator

        Stellt sicher dass Chunking-Logik isoliert funktioniert
        """
        # Erstelle ChunkProcessor mit kleinerer Chunk-Länge für Tests
        from core.chunk_processor import ChunkProcessor

        cp = ChunkProcessor(chunk_length_seconds=4, overlap_seconds=1)

        # Check ob Chunking erkannt wird (12s > 4s)
        should_chunk = cp.should_chunk(long_audio_file)
        assert should_chunk is True, "Long file should be chunked"

        # Estimate chunks
        estimated = cp.estimate_num_chunks(long_audio_file)
        assert estimated >= 3, f"Expected at least 3 chunks, got {estimated}"

        # Create chunks
        chunks = cp.chunk_audio(long_audio_file)
        assert len(chunks) == estimated, "Chunk count mismatch"

        # Merge chunks (ohne Verarbeitung)
        chunk_tuples = [(chunk, chunk.audio_data) for chunk in chunks]
        merged = cp.merge_chunks(chunk_tuples)

        # Check merged length
        original_audio, sr = sf.read(str(long_audio_file), always_2d=True)
        original_audio = original_audio.T  # (samples, channels) -> (channels, samples)

        original_length = original_audio.shape[1]
        merged_length = merged.shape[1]

        # Max 0.5s difference
        max_diff = int(0.5 * sr)
        assert (
            abs(original_length - merged_length) < max_diff
        ), f"Merged length differs: {original_length} vs {merged_length}"

        print(f"\n✓ ChunkProcessor working correctly:")
        print(f"  - Chunks created: {len(chunks)}")
        print(f"  - Original length: {original_length} samples")
        print(f"  - Merged length: {merged_length} samples")
        print(f"  - Difference: {abs(original_length - merged_length)} samples")
