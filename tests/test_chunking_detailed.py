#!/usr/bin/env python3
"""
Detailed test for chunking bug - bypasses should_chunk() and forces chunking
"""
import numpy as np
import soundfile as sf
from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).parent))

from core.chunk_processor import ChunkProcessor


def test_edge_case():
    """Test the specific edge case where chunks can be shorter than overlap"""
    print("\n" + "=" * 70)
    print("Testing EDGE CASE: Short chunks that trigger the bug")
    print("=" * 70)

    # Create audio that will produce a very short last chunk
    sample_rate = 44100

    # Scenario: 6.5 seconds audio with 4s chunks and 1s overlap
    # effective_chunk_size = 3s
    # num_chunks = ceil(6.5 / 3) = 3
    # Chunk 0: 0-4s (176400 samples)
    # Chunk 1: 3-7s, but limited to 6.5s = 3-6.5s (154350 samples)
    # Chunk 2: 6-10s, but limited to 6.5s = 6-6.5s (22050 samples) - SHORTER THAN OVERLAP!

    duration = 6.5
    chunk_length = 4
    overlap = 1

    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples)
    audio_data = np.sin(2 * np.pi * 440 * t)
    stereo_data = np.column_stack([audio_data, audio_data])

    temp_file = Path(tempfile.mktemp(suffix=".wav"))
    sf.write(str(temp_file), stereo_data, sample_rate)

    print(f"Created test audio: {duration}s at {sample_rate}Hz = {samples} samples")
    print(f"Chunk settings: length={chunk_length}s, overlap={overlap}s")
    print(f"Effective chunk size: {chunk_length - overlap}s")

    try:
        cp = ChunkProcessor(chunk_length_seconds=chunk_length, overlap_seconds=overlap)

        # Force chunking
        print("\n--- Chunking audio ---")
        chunks = cp.chunk_audio(temp_file)

        print(f"\nCreated {len(chunks)} chunks:")
        for i, chunk in enumerate(chunks):
            chunk_samples = chunk.audio_data.shape[1]
            chunk_duration = chunk_samples / chunk.sample_rate
            overlap_samples = int(overlap * sample_rate)

            is_short = chunk_samples < overlap_samples
            warning = " ⚠️  SHORTER THAN OVERLAP!" if is_short else ""

            print(
                f"  Chunk {i}: {chunk_samples} samples ({chunk_duration:.3f}s){warning}"
            )

        # Try to merge - this is where the bug would occur
        print("\n--- Merging chunks ---")
        chunk_tuples = [(chunk, chunk.audio_data) for chunk in chunks]

        merged_audio = cp.merge_chunks(chunk_tuples)

        merged_samples = merged_audio.shape[1]
        merged_duration = merged_samples / sample_rate

        print(f"Merged audio: {merged_samples} samples ({merged_duration:.3f}s)")

        # Verify length
        length_diff = abs(samples - merged_samples)
        length_diff_seconds = length_diff / sample_rate

        print(f"\nOriginal: {samples} samples ({duration:.3f}s)")
        print(f"Merged:   {merged_samples} samples ({merged_duration:.3f}s)")
        print(f"Difference: {length_diff} samples ({length_diff_seconds:.4f}s)")

        if length_diff_seconds < 0.1:
            print("\n✅ SUCCESS: Chunking and merging works correctly!")
            return True
        else:
            print("\n❌ FAIL: Significant length difference!")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        if temp_file.exists():
            temp_file.unlink()
        cp.cleanup_chunk_files()


def test_multiple_edge_cases():
    """Test various edge cases"""
    print("\n" + "=" * 70)
    print("Testing MULTIPLE EDGE CASES")
    print("=" * 70)

    test_cases = [
        # (duration, chunk_length, overlap, description)
        (6.5, 4, 1, "Last chunk shorter than overlap"),
        (8.2, 4, 1, "Last chunk slightly longer than overlap"),
        (10.5, 4, 1.5, "Last chunk with 1.5s overlap"),
        (15.1, 5, 2, "Multiple chunks with 2s overlap"),
    ]

    results = []
    for duration, chunk_length, overlap, description in test_cases:
        print(f"\n--- Test: {description} ---")
        print(f"    Duration: {duration}s, Chunk: {chunk_length}s, Overlap: {overlap}s")

        sample_rate = 44100
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)
        audio_data = np.sin(2 * np.pi * 440 * t)
        stereo_data = np.column_stack([audio_data, audio_data])

        temp_file = Path(tempfile.mktemp(suffix=".wav"))
        sf.write(str(temp_file), stereo_data, sample_rate)

        try:
            cp = ChunkProcessor(
                chunk_length_seconds=chunk_length, overlap_seconds=overlap
            )
            chunks = cp.chunk_audio(temp_file)

            print(f"    Created {len(chunks)} chunks")

            chunk_tuples = [(chunk, chunk.audio_data) for chunk in chunks]
            merged_audio = cp.merge_chunks(chunk_tuples)

            merged_samples = merged_audio.shape[1]
            length_diff = abs(samples - merged_samples)
            length_diff_seconds = length_diff / sample_rate

            success = length_diff_seconds < 0.1
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"    {status}: Length diff = {length_diff_seconds:.4f}s")

            results.append((description, success))

        except Exception as e:
            print(f"    ❌ ERROR: {e}")
            results.append((description, False))
        finally:
            if temp_file.exists():
                temp_file.unlink()
            cp.cleanup_chunk_files()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {description}")

    failed = sum(1 for _, success in results if not success)
    if failed == 0:
        print("\n✅ All edge case tests passed!")
        return True
    else:
        print(f"\n❌ {failed}/{len(results)} tests failed!")
        return False


if __name__ == "__main__":
    success1 = test_edge_case()
    success2 = test_multiple_edge_cases()

    if success1 and success2:
        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED! The chunking bug is fixed.")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("❌ SOME TESTS FAILED")
        print("=" * 70)
        sys.exit(1)
