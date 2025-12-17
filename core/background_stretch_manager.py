"""
Background Stretch Manager - Parallel time-stretching with priority queue

PURPOSE: Manage background processing of time-stretched loops for instant preview.
         Processes loops in priority order (Drums first) using thread pool.

CONTEXT: Integrated into Export Loops Widget for zero-latency preview.
         Automatically starts when user sets Target BPM.

ARCHITECTURE:
    User sets Target BPM
         ↓
    BackgroundStretchManager.start_batch()
         ↓
    Priority Queue (Drums priority=0, Vocals=1, Bass=2, Other=3)
         ↓
    Worker Thread Pool (4-8 parallel workers)
         ↓
    StretchCache (LRU eviction, 500 MB limit)
         ↓
    Preview/Export (instant access)

USAGE:
    >>> manager = BackgroundStretchManager(max_workers=4)
    >>> manager.progress_updated.connect(on_progress)
    >>> manager.all_completed.connect(on_completed)
    >>>
    >>> manager.start_batch(
    ...     stem_files={'drums': Path('drums.wav'), ...},
    ...     loop_segments=[(0.0, 9.23), (9.23, 18.46), ...],
    ...     original_bpm=104,
    ...     target_bpm=120,
    ...     sample_rate=44100
    ... )
    >>>
    >>> # Later: Get stretched loop
    >>> stretched = manager.get_stretched_loop('drums', 0, 120)
"""

from pathlib import Path
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass, field
from queue import PriorityQueue
import numpy as np
import soundfile as sf

from PySide6.QtCore import QObject, QThread, Signal, QMutex, QMutexLocker

from utils.logger import get_logger

logger = get_logger()


# ============================================================================
# Task Definition
# ============================================================================

@dataclass(order=True)
class StretchTask:
    """
    Task for background time-stretching.

    Priority-based processing order:
    - Priority 0: Drums (highest - most interesting for users)
    - Priority 1: Vocals
    - Priority 2: Bass
    - Priority 3: Other

    Attributes:
        priority: Task priority (0 = highest)
        stem_name: Stem name (e.g., 'drums', 'vocals')
        loop_index: Loop index (0-based)
        loop_start: Loop start time in seconds
        loop_end: Loop end time in seconds
        stem_path: Path to stem audio file
        original_bpm: Original BPM
        target_bpm: Target BPM
        sample_rate: Sample rate
        task_id: Unique task identifier
    """

    priority: int
    stem_name: str = field(compare=False)
    loop_index: int = field(compare=False)
    loop_start: float = field(compare=False)
    loop_end: float = field(compare=False)
    stem_path: Path = field(compare=False)
    original_bpm: float = field(compare=False)
    target_bpm: float = field(compare=False)
    sample_rate: int = field(compare=False)
    task_id: str = field(compare=False)


# ============================================================================
# Worker Thread
# ============================================================================

class StretchWorker(QThread):
    """
    Worker thread for time-stretching a single loop.

    Runs time-stretching in background thread to avoid blocking UI.
    Emits signals on completion or failure.
    """

    # Signals
    task_completed = Signal(str, np.ndarray)  # (task_id, stretched_audio)
    task_failed = Signal(str, str)  # (task_id, error_message)

    def __init__(self, task: StretchTask):
        """
        Initialize worker.

        Args:
            task: StretchTask to process
        """
        super().__init__()
        self.task = task

    def run(self):
        """
        Execute time-stretching task.

        Steps:
        1. Load loop segment from stem file
        2. Calculate stretch factor
        3. Time-stretch using core.time_stretcher
        4. Emit success or failure signal
        """

        try:
            # 1. Load loop segment from stem file
            audio_data, sr = sf.read(str(self.task.stem_path), always_2d=False)

            loop_start_sample = int(self.task.loop_start * sr)
            loop_end_sample = int(self.task.loop_end * sr)

            # Validate indices
            if loop_start_sample < 0 or loop_end_sample > len(audio_data):
                raise ValueError(
                    f"Invalid loop bounds: [{loop_start_sample}, {loop_end_sample}] "
                    f"for audio length {len(audio_data)}"
                )

            loop_audio = audio_data[loop_start_sample:loop_end_sample]

            if loop_audio.size == 0:
                raise ValueError("Extracted loop is empty")

            # 2. Calculate stretch factor
            from core.time_stretcher import calculate_stretch_factor

            stretch_factor = calculate_stretch_factor(
                self.task.original_bpm,
                self.task.target_bpm
            )

            # 3. Time-stretch
            from core.time_stretcher import time_stretch_audio, StretchQuality

            logger.debug(
                f"Processing: {self.task.stem_name}, Loop {self.task.loop_index}, "
                f"{self.task.original_bpm} → {self.task.target_bpm} BPM "
                f"(factor={stretch_factor:.2f})"
            )

            stretched_audio = time_stretch_audio(
                loop_audio,
                sr,
                stretch_factor,
                quality_preset=StretchQuality.EXPORT
            )

            # 4. Emit success
            logger.debug(
                f"Completed: {self.task.task_id}, "
                f"input={len(loop_audio)/sr:.2f}s, output={len(stretched_audio)/sr:.2f}s"
            )

            self.task_completed.emit(self.task.task_id, stretched_audio)

        except Exception as e:
            # Emit failure
            error_msg = f"Failed to stretch {self.task.task_id}: {e}"
            logger.error(error_msg, exc_info=True)
            self.task_failed.emit(self.task.task_id, str(e))


# ============================================================================
# Background Stretch Manager
# ============================================================================

class BackgroundStretchManager(QObject):
    """
    Manages background time-stretching of all loops.

    Features:
    - Priority-based processing (Drums first)
    - Thread pool for parallel processing
    - Progress tracking
    - Thread-safe result storage

    Signals:
        progress_updated(completed, total): Progress update
        all_completed(): All tasks finished
        task_completed(stem_name, loop_index, target_bpm): Single task finished
    """

    # Signals
    progress_updated = Signal(int, int)  # (completed_tasks, total_tasks)
    all_completed = Signal()
    task_completed = Signal(str, int, float)  # (stem_name, loop_index, target_bpm)

    def __init__(self, max_workers: int = 4):
        """
        Initialize background stretch manager.

        Args:
            max_workers: Maximum number of parallel worker threads
                        Default: 4 (good balance for most systems)
                        Recommended: CPU cores - 2 (leave cores for UI/system)
        """
        super().__init__()

        self.max_workers = max_workers
        self.task_queue = PriorityQueue()
        self.active_workers: List[StretchWorker] = []
        self.completed_tasks: Dict[str, np.ndarray] = {}  # task_id → audio
        self.failed_tasks: Dict[str, str] = {}  # task_id → error

        self.total_tasks = 0
        self.completed_count = 0

        self.is_running = False
        self.mutex = QMutex()

        logger.info(f"BackgroundStretchManager initialized with {max_workers} workers")

    def start_batch(
        self,
        stem_files: Dict[str, Path],
        loop_segments: List[Tuple[float, float]],
        original_bpm: float,
        target_bpm: float,
        sample_rate: int
    ):
        """
        Start background processing of all loops.

        Automatically creates tasks for all stems × loops and starts processing
        in priority order (Drums first).

        Args:
            stem_files: Dict of stem_name → stem_path
            loop_segments: List of (start_time, end_time) for each loop
            original_bpm: Original BPM from detection
            target_bpm: Target BPM from user input
            sample_rate: Sample rate
        """

        with QMutexLocker(self.mutex):
            # Clear previous state
            self._cancel_all_workers()
            self.task_queue = PriorityQueue()
            self.completed_tasks.clear()
            self.failed_tasks.clear()
            self.completed_count = 0

            # Define stem priority
            # WHY: Drums are most important for preview (rhythm-focused)
            stem_priority = {
                'drums': 0,    # Highest priority
                'vocals': 1,
                'bass': 2,
                'other': 3
            }

            # Create tasks for all loops × stems
            for stem_name, stem_path in stem_files.items():
                # Normalize stem name to lowercase for consistency
                # WHY: Task IDs must match between creation and retrieval.
                #      PlayerWidget uses lowercase when retrieving loops.
                stem_name_normalized = stem_name.lower()
                
                # Get priority (case-insensitive)
                priority = stem_priority.get(stem_name_normalized, 3)

                for loop_idx, (loop_start, loop_end) in enumerate(loop_segments):
                    # Use normalized stem name for task ID generation
                    task_id = self._generate_task_id(stem_name_normalized, loop_idx, target_bpm)

                    task = StretchTask(
                        priority=priority,
                        stem_name=stem_name_normalized,  # Store normalized name
                        loop_index=loop_idx,
                        loop_start=loop_start,
                        loop_end=loop_end,
                        stem_path=stem_path,
                        original_bpm=original_bpm,
                        target_bpm=target_bpm,
                        sample_rate=sample_rate,
                        task_id=task_id
                    )

                    self.task_queue.put(task)

            self.total_tasks = len(stem_files) * len(loop_segments)
            self.is_running = True

            logger.info(
                f"Started batch processing: {self.total_tasks} tasks "
                f"({len(stem_files)} stems × {len(loop_segments)} loops), "
                f"{original_bpm} → {target_bpm} BPM"
            )

            # Start processing
            self._start_next_workers()

            # Handle empty batch (0 tasks) - emit completion immediately
            if self.total_tasks == 0:
                self.is_running = False
                logger.info("Batch processing completed immediately (0 tasks)")
                self.all_completed.emit()

    def _start_next_workers(self):
        """
        Start next batch of workers from queue.

        ⚠️ IMPORTANT: This method MUST be called from within a mutex lock!
        It assumes the caller already holds self.mutex.

        Called by:
        - start_batch() (already locked at line 261)
        - _on_worker_finished() (already locked at line 379)
        """
        # NO mutex lock here - caller already has it!
        # This prevents deadlock when called from start_batch() or _on_worker_finished()

        while (
            len(self.active_workers) < self.max_workers
            and not self.task_queue.empty()
        ):
            # Get next task from priority queue
            task = self.task_queue.get()

            # Create and start worker
            worker = StretchWorker(task)
            worker.task_completed.connect(self._on_task_completed)
            worker.task_failed.connect(self._on_task_failed)
            worker.finished.connect(lambda w=worker: self._on_worker_finished(w))

            self.active_workers.append(worker)
            worker.start()

            logger.debug(
                f"Started worker: {task.task_id} "
                f"(priority={task.priority}, active={len(self.active_workers)})"
            )

    def _on_task_completed(self, task_id: str, stretched_audio: np.ndarray):
        """Handle completed task"""

        with QMutexLocker(self.mutex):
            self.completed_tasks[task_id] = stretched_audio
            self.completed_count += 1

            # Parse task_id to extract info
            stem_name, loop_index, target_bpm = self._parse_task_id(task_id)

            logger.debug(
                f"Task completed: {task_id} ({self.completed_count}/{self.total_tasks})"
            )

            # Emit signals
            self.progress_updated.emit(self.completed_count, self.total_tasks)
            self.task_completed.emit(stem_name, loop_index, target_bpm)

    def _on_task_failed(self, task_id: str, error_message: str):
        """Handle failed task"""

        with QMutexLocker(self.mutex):
            self.failed_tasks[task_id] = error_message
            self.completed_count += 1

            logger.warning(
                f"Task failed: {task_id} ({self.completed_count}/{self.total_tasks}) - {error_message}"
            )

            # Still emit progress (failed tasks count as completed)
            self.progress_updated.emit(self.completed_count, self.total_tasks)

    def _on_worker_finished(self, worker: StretchWorker):
        """Handle worker thread finished"""

        with QMutexLocker(self.mutex):
            if worker in self.active_workers:
                self.active_workers.remove(worker)

            # Start next worker
            self._start_next_workers()

            # Check if all tasks completed
            if self.completed_count >= self.total_tasks:
                self.is_running = False

                success_count = len(self.completed_tasks)
                failed_count = len(self.failed_tasks)

                logger.info(
                    f"Batch processing completed: {success_count} successful, "
                    f"{failed_count} failed"
                )

                self.all_completed.emit()

    def _cancel_all_workers(self):
        """Cancel all active workers"""

        for worker in self.active_workers:
            worker.terminate()
            worker.wait()

        self.active_workers.clear()
        logger.debug("All workers cancelled")

    def get_stretched_loop(
        self,
        stem_name: str,
        loop_index: int,
        target_bpm: float
    ) -> Optional[np.ndarray]:
        """
        Get stretched loop from completed tasks.

        Args:
            stem_name: Stem name
            loop_index: Loop index
            target_bpm: Target BPM

        Returns:
            Stretched audio array or None if not yet completed
        """

        task_id = self._generate_task_id(stem_name, loop_index, target_bpm)
        return self.completed_tasks.get(task_id)

    def is_loop_ready(
        self,
        stem_name: str,
        loop_index: int,
        target_bpm: float
    ) -> bool:
        """
        Check if specific loop is ready.

        Args:
            stem_name: Stem name
            loop_index: Loop index
            target_bpm: Target BPM

        Returns:
            True if loop is stretched and cached
        """

        task_id = self._generate_task_id(stem_name, loop_index, target_bpm)
        return task_id in self.completed_tasks

    def get_progress(self) -> Tuple[int, int]:
        """
        Get current progress.

        Returns:
            Tuple of (completed_tasks, total_tasks)
        """

        return (self.completed_count, self.total_tasks)

    def get_all_completed_loops(self) -> Dict[str, np.ndarray]:
        """
        Get all completed loops.

        Returns:
            Dict of task_id → stretched_audio
        """

        with QMutexLocker(self.mutex):
            return self.completed_tasks.copy()

    def cancel(self):
        """Cancel all background processing"""

        with QMutexLocker(self.mutex):
            self._cancel_all_workers()
            self.is_running = False
            logger.info("Background processing cancelled")

    @staticmethod
    def _generate_task_id(stem_name: str, loop_index: int, target_bpm: float) -> str:
        """Generate unique task ID"""
        return f"{stem_name}_{loop_index}_{int(target_bpm)}"

    @staticmethod
    def _parse_task_id(task_id: str) -> Tuple[str, int, float]:
        """
        Parse task ID.

        Args:
            task_id: Task ID (format: "stem_loopidx_bpm")

        Returns:
            Tuple of (stem_name, loop_index, target_bpm)
        """

        parts = task_id.split('_')
        if len(parts) < 3:
            raise ValueError(f"Invalid task_id format: {task_id}")

        stem_name = parts[0]
        loop_index = int(parts[1])
        target_bpm = float(parts[2])

        return (stem_name, loop_index, target_bpm)


# ============================================================================
# Utility Functions
# ============================================================================

def get_optimal_worker_count() -> int:
    """
    Calculate optimal worker count based on CPU cores.

    Returns:
        Recommended worker count

    Algorithm:
        - Leave 1-2 cores for UI/system
        - Cap at 8 workers (diminishing returns beyond that)

    Example:
        >>> # 8-core system
        >>> get_optimal_worker_count()
        6  # 8 cores - 2 for UI/system
    """

    import multiprocessing

    cpu_count = multiprocessing.cpu_count()

    # Leave 1-2 cores for UI/system
    optimal = max(2, cpu_count - 2)

    # Cap at 8 workers (diminishing returns, thread overhead)
    return min(optimal, 8)
