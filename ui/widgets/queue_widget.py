"""
Queue Widget - Task queue management for batch separation

PURPOSE: Allow users to queue multiple files for sequential processing.
CONTEXT: Manages separation tasks and shows progress for each queued item.
"""
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum
from collections import deque
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot, QRunnable, QThreadPool, QObject

from ui.app_context import AppContext
from core.separator import SeparationResult


class TaskStatus(Enum):
    """Status of a queued task"""
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


@dataclass
class QueueTask:
    """Represents a task in the queue"""
    file_path: Path
    model_id: str
    output_dir: Optional[Path] = None
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    result: Optional[SeparationResult] = None
    error_message: Optional[str] = None


class QueueSignals(QObject):
    """Signals for queue worker"""
    task_started = Signal(int)  # task_index
    task_progress = Signal(int, str, int)  # (task_index, message, percent)
    task_finished = Signal(int, object)  # (task_index, SeparationResult)
    task_error = Signal(int, str)  # (task_index, error_message)
    queue_finished = Signal()


class QueueWorker(QRunnable):
    """
    Worker for processing queue in background
    
    WHY: Queue processing is long-running and must not block GUI
    """
    
    def __init__(self, tasks: List[QueueTask]):
        super().__init__()
        self.tasks = tasks
        self.signals = QueueSignals()
        self.ctx = AppContext()
        self.should_stop = False
    
    def run(self):
        """Process all tasks in queue"""
        separator = self.ctx.separator()
        
        for index, task in enumerate(self.tasks):
            if self.should_stop:
                break
            
            if task.status != TaskStatus.PENDING:
                continue
            
            self.signals.task_started.emit(index)
            
            try:
                # Progress callback for this task
                def progress_callback(message: str, percent: int):
                    self.signals.task_progress.emit(index, message, percent)
                
                # Get quality preset from settings
                settings_mgr = self.ctx.settings_manager()
                quality_preset = settings_mgr.get_quality_preset()

                # Run separation
                result = separator.separate(
                    audio_file=task.file_path,
                    model_id=task.model_id,
                    output_dir=task.output_dir,
                    quality_preset=quality_preset,
                    progress_callback=progress_callback
                )
                
                self.signals.task_finished.emit(index, result)
                
            except Exception as e:
                self.ctx.logger().error(f"Queue task {index} error: {e}", exc_info=True)
                self.signals.task_error.emit(index, str(e))
        
        self.signals.queue_finished.emit()
    
    def stop(self):
        """Request worker to stop"""
        self.should_stop = True


class QueueWidget(QWidget):
    """
    Widget for managing separation task queue
    
    Features:
    - Add files to queue (from signals)
    - View queue with status
    - Start/stop queue processing
    - Clear queue
    - View individual task progress
    - Reorder tasks (future)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = AppContext()
        self.tasks: List[QueueTask] = []
        self.thread_pool = QThreadPool()
        self.current_worker: Optional[QueueWorker] = None
        self.is_processing = False
        
        self._setup_ui()
        self._connect_signals()
        self.apply_translations()
        
        self.ctx.logger().info("QueueWidget initialized")
    
    def _setup_ui(self):
        """Setup widget layout and components"""
        layout = QVBoxLayout(self)
        
        # Queue Table
        table_group = QGroupBox("Task Queue")
        table_layout = QVBoxLayout()
        
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(5)
        self.queue_table.setHorizontalHeaderLabels(
            ["File", "Model", "Status", "Progress", "Result"]
        )
        self.queue_table.horizontalHeader().setStretchLastSection(True)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_table.setSelectionMode(QTableWidget.SingleSelection)
        
        # Set column widths
        header = self.queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.queue_table.setColumnWidth(3, 150)
        
        table_layout.addWidget(self.queue_table)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        # Controls
        controls_group = QGroupBox("Controls")
        controls_layout = QVBoxLayout()
        
        # Status label
        self.status_label = QLabel("Queue empty")
        controls_layout.addWidget(self.status_label)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        self.btn_start = QPushButton("Start Queue")
        self.btn_start.setEnabled(False)
        self.btn_stop = QPushButton("Stop Queue")
        self.btn_stop.setEnabled(False)
        self.btn_clear = QPushButton("Clear Queue")
        self.btn_remove = QPushButton("Remove Selected")
        
        buttons_layout.addWidget(self.btn_start)
        buttons_layout.addWidget(self.btn_stop)
        buttons_layout.addWidget(self.btn_clear)
        buttons_layout.addWidget(self.btn_remove)
        buttons_layout.addStretch()
        controls_layout.addLayout(buttons_layout)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
    
    def _connect_signals(self):
        """Connect button signals"""
        self.btn_start.clicked.connect(self._on_start_queue)
        self.btn_stop.clicked.connect(self._on_stop_queue)
        self.btn_clear.clicked.connect(self._on_clear_queue)
        self.btn_remove.clicked.connect(self._on_remove_selected)
    
    def add_task(self, file_path: Path, model_id: str, output_dir: Optional[Path] = None):
        """
        Add task to queue
        
        WHY: External components (upload widget) can queue files for batch processing
        """
        task = QueueTask(
            file_path=file_path,
            model_id=model_id,
            output_dir=output_dir
        )
        
        self.tasks.append(task)
        self._add_table_row(task)
        self._update_status()
        
        self.ctx.logger().info(f"Task added to queue: {file_path.name}")
    
    def _add_table_row(self, task: QueueTask):
        """Add task to table"""
        row = self.queue_table.rowCount()
        self.queue_table.insertRow(row)
        
        # File name
        self.queue_table.setItem(row, 0, QTableWidgetItem(task.file_path.name))
        
        # Model
        model_manager = self.ctx.model_manager()
        model_info = model_manager.get_model_info(task.model_id)
        model_name = model_info.name if model_info else task.model_id
        self.queue_table.setItem(row, 1, QTableWidgetItem(model_name))
        
        # Status
        self.queue_table.setItem(row, 2, QTableWidgetItem(task.status.value))
        
        # Progress bar
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        self.queue_table.setCellWidget(row, 3, progress_bar)
        
        # Result
        self.queue_table.setItem(row, 4, QTableWidgetItem(""))
    
    def _update_table_row(self, index: int):
        """Update table row for task"""
        if index >= len(self.tasks):
            return
        
        task = self.tasks[index]
        
        # Status
        status_item = self.queue_table.item(index, 2)
        if status_item:
            status_item.setText(task.status.value)
        
        # Progress
        progress_bar = self.queue_table.cellWidget(index, 3)
        if isinstance(progress_bar, QProgressBar):
            progress_bar.setValue(task.progress)
        
        # Result
        result_text = ""
        if task.status == TaskStatus.COMPLETED and task.result:
            result_text = f"✓ {len(task.result.stems)} stems ({task.result.duration_seconds:.1f}s)"
        elif task.status == TaskStatus.FAILED:
            result_text = f"✗ {task.error_message or 'Error'}"
        
        result_item = self.queue_table.item(index, 4)
        if result_item:
            result_item.setText(result_text)
    
    @Slot()
    def _on_start_queue(self):
        """
        Start processing queue
        
        WHY: Processes all pending tasks sequentially in background thread
        """
        if self.is_processing:
            return
        
        # Get pending tasks
        pending_tasks = [t for t in self.tasks if t.status == TaskStatus.PENDING]
        
        if not pending_tasks:
            QMessageBox.information(
                self,
                "No Tasks",
                "No pending tasks in queue"
            )
            return
        
        self.is_processing = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_clear.setEnabled(False)
        
        # Create worker
        worker = QueueWorker(self.tasks)
        worker.signals.task_started.connect(self._on_task_started)
        worker.signals.task_progress.connect(self._on_task_progress)
        worker.signals.task_finished.connect(self._on_task_finished)
        worker.signals.task_error.connect(self._on_task_error)
        worker.signals.queue_finished.connect(self._on_queue_finished)
        
        self.current_worker = worker
        self.thread_pool.start(worker)
        
        self.ctx.logger().info(f"Queue processing started: {len(pending_tasks)} tasks")
    
    @Slot()
    def _on_stop_queue(self):
        """Stop queue processing"""
        if self.current_worker:
            self.current_worker.stop()
            self.status_label.setText("Stopping queue...")
    
    @Slot()
    def _on_clear_queue(self):
        """Clear all tasks from queue"""
        if not self.tasks:
            return
        
        reply = QMessageBox.question(
            self,
            "Clear Queue",
            f"Remove all {len(self.tasks)} tasks from queue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.tasks.clear()
            self.queue_table.setRowCount(0)
            self._update_status()
    
    @Slot()
    def _on_remove_selected(self):
        """Remove selected task from queue"""
        selected_rows = self.queue_table.selectedIndexes()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        
        if 0 <= row < len(self.tasks):
            task = self.tasks[row]
            
            # Don't allow removing currently processing task
            if task.status == TaskStatus.PROCESSING:
                QMessageBox.warning(
                    self,
                    "Cannot Remove",
                    "Cannot remove task that is currently processing"
                )
                return
            
            self.tasks.pop(row)
            self.queue_table.removeRow(row)
            self._update_status()
    
    @Slot(int)
    def _on_task_started(self, index: int):
        """Handle task start"""
        if index < len(self.tasks):
            self.tasks[index].status = TaskStatus.PROCESSING
            self._update_table_row(index)
            self._update_status()
    
    @Slot(int, str, int)
    def _on_task_progress(self, index: int, message: str, percent: int):
        """Handle task progress update"""
        if index < len(self.tasks):
            self.tasks[index].progress = percent
            self._update_table_row(index)
            self.status_label.setText(f"Processing {index + 1}/{len(self.tasks)}: {message}")
    
    @Slot(int, object)
    def _on_task_finished(self, index: int, result: SeparationResult):
        """Handle task completion"""
        if index < len(self.tasks):
            task = self.tasks[index]
            task.result = result
            
            if result.success:
                task.status = TaskStatus.COMPLETED
                task.progress = 100
            else:
                task.status = TaskStatus.FAILED
                task.error_message = result.error_message
            
            self._update_table_row(index)
            self._update_status()
    
    @Slot(int, str)
    def _on_task_error(self, index: int, error_message: str):
        """Handle task error"""
        if index < len(self.tasks):
            self.tasks[index].status = TaskStatus.FAILED
            self.tasks[index].error_message = error_message
            self._update_table_row(index)
            self._update_status()
    
    @Slot()
    def _on_queue_finished(self):
        """Handle queue completion"""
        self.is_processing = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_clear.setEnabled(True)
        self.current_worker = None
        
        # Count results
        completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        
        self.status_label.setText(f"Queue finished: {completed} completed, {failed} failed")
        
        QMessageBox.information(
            self,
            "Queue Complete",
            f"Queue processing finished!\n\n"
            f"Completed: {completed}\n"
            f"Failed: {failed}"
        )
        
        self.ctx.logger().info(f"Queue finished: {completed} completed, {failed} failed")
    
    def _update_status(self):
        """Update status label and button states"""
        if not self.tasks:
            self.status_label.setText("Queue empty")
            self.btn_start.setEnabled(False)
            self.btn_clear.setEnabled(False)
            return
        
        pending = sum(1 for t in self.tasks if t.status == TaskStatus.PENDING)
        processing = sum(1 for t in self.tasks if t.status == TaskStatus.PROCESSING)
        completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        
        self.status_label.setText(
            f"{len(self.tasks)} tasks: "
            f"{pending} pending, {processing} processing, "
            f"{completed} completed, {failed} failed"
        )
        
        self.btn_start.setEnabled(pending > 0 and not self.is_processing)
        self.btn_clear.setEnabled(not self.is_processing)
    
    def apply_translations(self):
        """Apply current language translations"""
        # Translation keys would be defined in resources/translations/*.json
        pass

