"""
Unit tests for core.background_stretch_manager module

Tests cover:
- Task creation and priority
- Worker execution
- Background manager orchestration
- Thread-safe result storage
- Progress tracking
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import soundfile as sf
import time

from PySide6.QtCore import QObject, QEventLoop, QTimer

from core.background_stretch_manager import (
    StretchTask,
    StretchWorker,
    BackgroundStretchManager,
    get_optimal_worker_count
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_audio_file():
    """Create temporary audio file with test data"""
    # Generate 0.5 seconds of audio (optimized for fast tests)
    sr = 44100
    duration = 0.5  # Reduced from 2.0 to 0.5 seconds
    samples = int(sr * duration)
    audio = np.sin(2 * np.pi * 440 * np.linspace(0, duration, samples)).astype(np.float32)
    audio = np.stack([audio, audio], axis=1)  # Stereo

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        sf.write(f.name, audio, sr)
        yield Path(f.name)

    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def stem_files(sample_audio_file):
    """Create multiple stem files for testing"""
    # Use same file for 2 stems (reduced from 4 for faster tests)
    return {
        'drums': sample_audio_file,
        'vocals': sample_audio_file
    }


@pytest.fixture
def loop_segments():
    """Create test loop segments"""
    # 2 loops of 0.25 seconds each (reduced from 3 for faster tests)
    return [
        (0.0, 0.25),
        (0.25, 0.5)
    ]


# ============================================================================
# Test: Task Creation and Priority
# ============================================================================

def test_stretch_task_creation():
    """Test StretchTask creation"""
    task = StretchTask(
        priority=0,
        stem_name='drums',
        loop_index=0,
        loop_start=0.0,
        loop_end=10.0,
        stem_path=Path('/tmp/drums.wav'),
        original_bpm=104.0,
        target_bpm=120.0,
        sample_rate=44100,
        task_id='drums_0_120'
    )

    assert task.priority == 0
    assert task.stem_name == 'drums'
    assert task.loop_index == 0
    assert task.task_id == 'drums_0_120'


def test_stretch_task_priority_ordering():
    """Test that tasks are ordered by priority"""
    from queue import PriorityQueue

    queue = PriorityQueue()

    # Add tasks in random order
    vocals_task = StretchTask(1, 'vocals', 0, 0, 1, Path('v.wav'), 104, 120, 44100, 'v_0_120')
    drums_task = StretchTask(0, 'drums', 0, 0, 1, Path('d.wav'), 104, 120, 44100, 'd_0_120')
    other_task = StretchTask(3, 'other', 0, 0, 1, Path('o.wav'), 104, 120, 44100, 'o_0_120')

    queue.put(vocals_task)
    queue.put(drums_task)
    queue.put(other_task)

    # Should come out in priority order (drums first)
    first = queue.get()
    assert first.stem_name == 'drums'


# ============================================================================
# Test: Worker Execution
# ============================================================================

def test_worker_successful_execution(qtbot, sample_audio_file):
    """Test successful worker execution"""
    task = StretchTask(
        priority=0,
        stem_name='drums',
        loop_index=0,
        loop_start=0.0,
        loop_end=0.5,  # 0.5 second loop
        stem_path=sample_audio_file,
        original_bpm=104.0,
        target_bpm=120.0,
        sample_rate=44100,
        task_id='drums_0_120'
    )

    worker = StretchWorker(task)

    # Track completion
    completed = []

    def on_completed(task_id, audio):
        completed.append((task_id, audio))

    worker.task_completed.connect(on_completed)

    # Start worker
    worker.start()

    # Wait for completion (with timeout)
    qtbot.waitUntil(lambda: len(completed) > 0, timeout=10000)

    # Verify result
    assert len(completed) == 1
    task_id, audio = completed[0]
    assert task_id == 'drums_0_120'
    assert audio.size > 0


def test_worker_failure_handling(qtbot):
    """Test worker error handling"""
    # Create task with invalid file
    task = StretchTask(
        priority=0,
        stem_name='drums',
        loop_index=0,
        loop_start=0.0,
        loop_end=0.5,
        stem_path=Path('/nonexistent/file.wav'),  # Invalid path
        original_bpm=104.0,
        target_bpm=120.0,
        sample_rate=44100,
        task_id='drums_0_120'
    )

    worker = StretchWorker(task)

    # Track failures
    failures = []

    def on_failed(task_id, error):
        failures.append((task_id, error))

    worker.task_failed.connect(on_failed)

    # Start worker
    worker.start()

    # Wait for failure
    qtbot.waitUntil(lambda: len(failures) > 0, timeout=5000)

    # Verify error was caught
    assert len(failures) == 1
    task_id, error = failures[0]
    assert task_id == 'drums_0_120'
    assert error != ''


# ============================================================================
# Test: Background Manager
# ============================================================================

def test_background_manager_initialization():
    """Test BackgroundStretchManager initialization"""
    manager = BackgroundStretchManager(max_workers=4)

    assert manager.max_workers == 4
    assert manager.is_running is False
    assert manager.total_tasks == 0
    assert manager.completed_count == 0


def test_background_manager_start_batch(qtbot, stem_files, loop_segments):
    """Test starting batch processing"""
    manager = BackgroundStretchManager(max_workers=2)

    # Track completion
    all_completed = []

    def on_all_completed():
        all_completed.append(True)

    manager.all_completed.connect(on_all_completed)

    # Start batch
    manager.start_batch(
        stem_files=stem_files,
        loop_segments=loop_segments,
        original_bpm=104,
        target_bpm=120,
        sample_rate=44100
    )

    # Verify batch started
    assert manager.is_running is True
    assert manager.total_tasks == 4  # 2 stems × 2 loops (reduced for faster tests)

    # Wait for completion (with longer timeout for processing)
    qtbot.waitUntil(lambda: len(all_completed) > 0, timeout=30000)

    # Verify all tasks completed
    assert manager.is_running is False
    assert manager.completed_count == 4


def test_background_manager_progress_tracking(qtbot, stem_files, loop_segments):
    """Test progress tracking"""
    manager = BackgroundStretchManager(max_workers=2)

    # Track progress updates
    progress_updates = []

    def on_progress(completed, total):
        progress_updates.append((completed, total))

    manager.progress_updated.connect(on_progress)

    # Start batch
    manager.start_batch(
        stem_files=stem_files,
        loop_segments=loop_segments,
        original_bpm=104,
        target_bpm=120,
        sample_rate=44100
    )

    # Wait for completion
    qtbot.waitUntil(lambda: manager.completed_count == manager.total_tasks, timeout=30000)

    # Verify progress was tracked
    assert len(progress_updates) > 0
    assert progress_updates[-1] == (4, 4)  # Final update (2 stems × 2 loops)


def test_background_manager_priority_processing(qtbot, stem_files, loop_segments):
    """Test that drums are processed first (priority)"""
    manager = BackgroundStretchManager(max_workers=1)  # Single worker to ensure order

    # Track task completion order
    completed_tasks = []

    def on_task_completed(stem_name, loop_index, target_bpm):
        completed_tasks.append(stem_name)

    manager.task_completed.connect(on_task_completed)

    # Start batch
    manager.start_batch(
        stem_files=stem_files,
        loop_segments=loop_segments,
        original_bpm=104,
        target_bpm=120,
        sample_rate=44100
    )

    # Wait for completion
    qtbot.waitUntil(lambda: len(completed_tasks) == 4, timeout=30000)

    # First 2 tasks should be drums (all drum loops processed first)
    assert completed_tasks[0] == 'drums'
    assert completed_tasks[1] == 'drums'


def test_background_manager_get_stretched_loop(qtbot, stem_files, loop_segments):
    """Test retrieving stretched loops"""
    manager = BackgroundStretchManager(max_workers=2)

    # Start batch
    manager.start_batch(
        stem_files=stem_files,
        loop_segments=loop_segments,
        original_bpm=104,
        target_bpm=120,
        sample_rate=44100
    )

    # Wait for completion
    qtbot.waitUntil(lambda: manager.completed_count == manager.total_tasks, timeout=30000)

    # Retrieve specific loop
    stretched = manager.get_stretched_loop('drums', 0, 120)

    assert stretched is not None
    assert stretched.size > 0


def test_background_manager_is_loop_ready(qtbot, stem_files, loop_segments):
    """Test checking if loop is ready"""
    manager = BackgroundStretchManager(max_workers=2)

    # Initially not ready
    assert manager.is_loop_ready('drums', 0, 120) is False

    # Start batch
    manager.start_batch(
        stem_files=stem_files,
        loop_segments=loop_segments,
        original_bpm=104,
        target_bpm=120,
        sample_rate=44100
    )

    # Wait for completion
    qtbot.waitUntil(lambda: manager.completed_count == manager.total_tasks, timeout=30000)

    # Should be ready now
    assert manager.is_loop_ready('drums', 0, 120) is True


def test_background_manager_cancel(qtbot, stem_files, loop_segments):
    """Test canceling background processing"""
    manager = BackgroundStretchManager(max_workers=2)

    # Start batch
    manager.start_batch(
        stem_files=stem_files,
        loop_segments=loop_segments,
        original_bpm=104,
        target_bpm=120,
        sample_rate=44100
    )

    assert manager.is_running is True

    # Cancel immediately
    manager.cancel()

    # Should be stopped
    assert manager.is_running is False


# ============================================================================
# Test: Utility Functions
# ============================================================================

def test_get_optimal_worker_count():
    """Test optimal worker count calculation"""
    count = get_optimal_worker_count()

    # Should be reasonable
    assert count >= 2
    assert count <= 8


# ============================================================================
# Test: Task ID Generation and Parsing
# ============================================================================

def test_generate_task_id():
    """Test task ID generation"""
    task_id = BackgroundStretchManager._generate_task_id('drums', 3, 120.5)
    assert task_id == 'drums_3_120'


def test_parse_task_id():
    """Test task ID parsing"""
    stem, loop_idx, bpm = BackgroundStretchManager._parse_task_id('drums_3_120')

    assert stem == 'drums'
    assert loop_idx == 3
    assert bpm == 120.0


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_background_manager_empty_batch():
    """Test starting batch with no stems"""
    manager = BackgroundStretchManager(max_workers=2)

    # Start with empty stems
    manager.start_batch(
        stem_files={},
        loop_segments=[],
        original_bpm=104,
        target_bpm=120,
        sample_rate=44100
    )

    # Should handle gracefully
    assert manager.total_tasks == 0
    assert manager.is_running is False  # Finishes immediately with 0 tasks


def test_background_manager_multiple_batches(qtbot, stem_files, loop_segments):
    """Test running multiple batches sequentially"""
    manager = BackgroundStretchManager(max_workers=2)

    # First batch
    manager.start_batch(
        stem_files=stem_files,
        loop_segments=loop_segments,
        original_bpm=104,
        target_bpm=120,
        sample_rate=44100
    )

    qtbot.waitUntil(lambda: manager.completed_count == manager.total_tasks, timeout=30000)

    # Second batch (should clear first)
    manager.start_batch(
        stem_files=stem_files,
        loop_segments=loop_segments,
        original_bpm=120,
        target_bpm=140,
        sample_rate=44100
    )

    # Should restart correctly
    assert manager.total_tasks == 4  # 2 stems × 2 loops
    assert manager.completed_count < manager.total_tasks  # Processing


def test_background_manager_get_all_completed(qtbot, stem_files, loop_segments):
    """Test getting all completed loops"""
    manager = BackgroundStretchManager(max_workers=2)

    manager.start_batch(
        stem_files=stem_files,
        loop_segments=loop_segments,
        original_bpm=104,
        target_bpm=120,
        sample_rate=44100
    )

    qtbot.waitUntil(lambda: manager.completed_count == manager.total_tasks, timeout=30000)

    # Get all completed
    all_loops = manager.get_all_completed_loops()

    assert len(all_loops) == 4  # All 4 tasks (2 stems × 2 loops)
    assert 'drums_0_120' in all_loops
    assert 'vocals_1_120' in all_loops  # Loop indices: 0, 1
