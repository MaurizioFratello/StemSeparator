#!/usr/bin/env python3
"""
Simple integration test for BackgroundStretchManager
Tests real audio processing without pytest-qt complications
"""

import sys
import time
import tempfile
import numpy as np
import soundfile as sf
from pathlib import Path

# Add project to path
sys.path.insert(0, '/Users/moritzbruder/Documents/04_Python/StemSeparator')

from core.background_stretch_manager import BackgroundStretchManager
from PySide6.QtWidgets import QApplication

def create_test_audio():
    """Create temporary audio file with test data"""
    sr = 44100
    duration = 0.5  # 0.5 seconds
    samples = int(sr * duration)
    audio = np.sin(2 * np.pi * 440 * np.linspace(0, duration, samples)).astype(np.float32)
    audio = np.stack([audio, audio], axis=1)  # Stereo

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        sf.write(f.name, audio, sr)
        return Path(f.name)

def main():
    print("=" * 60)
    print("SIMPLE INTEGRATION TEST - BackgroundStretchManager")
    print("=" * 60)

    # Create QApplication (required for Qt signals)
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Create test audio
    print("\n1. Creating test audio files...")
    audio_file = create_test_audio()
    print(f"   ✓ Created: {audio_file}")

    # Setup test data
    stem_files = {
        'drums': audio_file,
        'vocals': audio_file
    }
    loop_segments = [
        (0.0, 0.25),
        (0.25, 0.5)
    ]

    print(f"\n2. Test configuration:")
    print(f"   - Stems: {len(stem_files)}")
    print(f"   - Loops: {len(loop_segments)}")
    print(f"   - Total tasks: {len(stem_files) * len(loop_segments)}")
    print(f"   - Original BPM: 104")
    print(f"   - Target BPM: 120")

    # Create manager
    print(f"\n3. Creating BackgroundStretchManager...")
    manager = BackgroundStretchManager(max_workers=2)
    print(f"   ✓ Manager created with {manager.max_workers} workers")

    # Track completion
    completed = []
    def on_all_completed():
        completed.append(True)
        print(f"\n   🎉 ALL COMPLETED signal received!")

    progress_updates = []
    def on_progress(current, total):
        progress_updates.append((current, total))
        print(f"   Progress: {current}/{total} ({int(current/total*100)}%)")

    manager.all_completed.connect(on_all_completed)
    manager.progress_updated.connect(on_progress)

    # Start batch
    print(f"\n4. Starting batch processing...")
    manager.start_batch(
        stem_files=stem_files,
        loop_segments=loop_segments,
        original_bpm=104,
        target_bpm=120,
        sample_rate=44100
    )

    print(f"   ✓ Batch started")
    print(f"   - is_running: {manager.is_running}")
    print(f"   - total_tasks: {manager.total_tasks}")

    # Wait for completion (simple polling, no qtbot)
    print(f"\n5. Waiting for completion (max 60s)...")
    start_time = time.time()
    timeout = 60

    while manager.is_running and (time.time() - start_time) < timeout:
        # Process Qt events
        app.processEvents()
        time.sleep(0.1)

    elapsed = time.time() - start_time

    # Check results
    print(f"\n6. Results:")
    print(f"   - Elapsed time: {elapsed:.1f}s")
    print(f"   - is_running: {manager.is_running}")
    print(f"   - completed_count: {manager.completed_count}")
    print(f"   - total_tasks: {manager.total_tasks}")
    print(f"   - Progress updates: {len(progress_updates)}")
    print(f"   - All completed signal: {len(completed)}")

    # Verify
    print(f"\n7. Verification:")
    success = True

    if manager.is_running:
        print(f"   ✗ FAIL: Manager still running after {timeout}s")
        success = False
    else:
        print(f"   ✓ Manager stopped")

    if manager.completed_count != manager.total_tasks:
        print(f"   ✗ FAIL: Only {manager.completed_count}/{manager.total_tasks} tasks completed")
        success = False
    else:
        print(f"   ✓ All {manager.total_tasks} tasks completed")

    if len(completed) == 0:
        print(f"   ✗ FAIL: all_completed signal not received")
        success = False
    else:
        print(f"   ✓ all_completed signal received")

    # Test retrieval
    stretched = manager.get_stretched_loop('drums', 0, 120)
    if stretched is None:
        print(f"   ✗ FAIL: Could not retrieve stretched loop")
        success = False
    else:
        print(f"   ✓ Retrieved stretched loop ({stretched.size} samples)")

    # Cleanup
    print(f"\n8. Cleanup...")
    audio_file.unlink()
    print(f"   ✓ Cleaned up test files")

    # Final result
    print(f"\n" + "=" * 60)
    if success:
        print("✅ INTEGRATION TEST PASSED!")
        print("=" * 60)
        return 0
    else:
        print("❌ INTEGRATION TEST FAILED!")
        print("=" * 60)
        return 1

if __name__ == '__main__':
    sys.exit(main())
