"""
Upload Widget - File selection, model configuration, and separation control

PURPOSE: Allow users to select audio files, choose separation model, and initiate processing.
CONTEXT: Primary workflow entry point for file-based separation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, List
import soundfile as sf
import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QLineEdit,
    QProgressBar,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QCheckBox,
    QScrollArea,
    QFrame,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, Slot, QObject
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from ui.app_context import AppContext
from ui.widgets.waveform_widget import WaveformWidget
from config import ENSEMBLE_CONFIGS
from ui.theme import ThemeManager


class DragDropListWidget(QListWidget):
    """
    QListWidget with drag-and-drop support for audio files

    WHY: QListWidget doesn't support drag-and-drop by default for external files
    """

    files_dropped = Signal(list)  # Emits list of Path objects

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Accept drag events with file URLs"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Accept drag move events with file URLs"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle dropped files"""
        if event.mimeData().hasUrls():
            file_paths = []
            for url in event.mimeData().urls():
                file_path = Path(url.toLocalFile())
                if file_path.exists() and file_path.is_file():
                    file_paths.append(file_path)

            if file_paths:
                self.files_dropped.emit(file_paths)
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()


class UploadWidget(QWidget):
    """
    Widget for file upload and separation configuration

    Features:
    - Drag & drop file selection
    - File browser dialog
    - Model selection dropdown
    - Output directory configuration
    - Progress tracking
    - Queue integration (signal)
    """

    # Signal emitted when user wants to queue a file
    file_queued = Signal(
        Path, str, bool, str
    )  # (file_path, model_id, use_ensemble, ensemble_config)
    # Signal to request queue processing start
    start_queue_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = AppContext()

        self._setup_ui()
        self._connect_signals()
        self._load_models()
        self.apply_translations()

        self.ctx.logger().info("UploadWidget initialized")

    def _create_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a styled card frame with header"""
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QLabel(title)
        header.setObjectName("card_header")
        layout.addWidget(header)

        return card, layout

    def _setup_ui(self):
        """Setup widget layout and components"""
        # Create main layout for the widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)  # Add padding
        main_layout.setSpacing(15)

        # File Selection Card
        file_card, file_layout = self._create_card("Audio File")

        # Drag & Drop area
        self.file_list = DragDropListWidget()
        self.file_list.setDragEnabled(True)
        # self.file_list.setMaximumHeight(150)  # Remove fixed height to allow resizing
        file_layout.addWidget(self.file_list)

        # File buttons
        file_buttons = QHBoxLayout()
        self.btn_browse = QPushButton("Browse...")
        ThemeManager.set_widget_property(self.btn_browse, "buttonStyle", "secondary")
        self.btn_browse.setToolTip("Select audio files to separate")

        self.btn_remove_selected = QPushButton("Remove Selected")
        ThemeManager.set_widget_property(
            self.btn_remove_selected, "buttonStyle", "secondary"
        )
        self.btn_remove_selected.setToolTip(
            "Remove selected files from list (available when files are selected)"
        )

        self.btn_clear = QPushButton("Clear All")
        ThemeManager.set_widget_property(self.btn_clear, "buttonStyle", "secondary")
        self.btn_clear.setToolTip(
            "Clear all files from list (available when files are present)"
        )
        file_buttons.addWidget(self.btn_browse)
        file_buttons.addWidget(self.btn_remove_selected)
        file_buttons.addWidget(self.btn_clear)
        file_buttons.addStretch()
        file_layout.addLayout(file_buttons)

        main_layout.addWidget(file_card, stretch=1)  # Allow this card to expand

        # Waveform Widget (hidden by default, shown when file is selected)
        self.waveform_widget = WaveformWidget()
        main_layout.addWidget(self.waveform_widget)

        # Configuration Card
        config_card, config_layout = self._create_card("Separation Settings")
        config_layout.setSpacing(10)  # Tighter spacing for config card

        # Ensemble Checkbox (own row to prevent dropdown overlap)
        self.ensemble_checkbox = QCheckBox("Ensemble Mode")
        self.ensemble_checkbox.setToolTip("Combine models for higher quality (slower)")
        config_layout.addWidget(self.ensemble_checkbox)

        # Model/Config Selection (separate row below checkbox)
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        model_row.addWidget(self.model_combo, stretch=1)
        config_layout.addLayout(model_row)

        # Ensemble config dropdown (hidden/shown dynamically)
        # We reuse the same combo box logic but change contents based on mode

        # Output directory
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output:"))
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Default: temp/separated")
        output_layout.addWidget(self.output_path, stretch=1)
        self.btn_output_browse = QPushButton("Browse...")
        output_layout.addWidget(self.btn_output_browse)
        config_layout.addLayout(output_layout)

        main_layout.addWidget(config_card)

        # Progress Card is removed as status is now in the global queue drawer

        # Action Buttons
        action_layout = QHBoxLayout()
        self.btn_start = QPushButton("▶ Start Separation")
        self.btn_start.setEnabled(False)
        # Primary button uses default gradient style

        self.btn_queue = QPushButton("➕ Add to Queue")
        self.btn_queue.setEnabled(False)
        ThemeManager.set_widget_property(self.btn_queue, "buttonStyle", "secondary")

        action_layout.addWidget(self.btn_start)
        action_layout.addWidget(self.btn_queue)
        action_layout.addStretch()
        main_layout.addLayout(action_layout)

    def _connect_signals(self):
        """Connect button signals to handlers"""
        self.btn_browse.clicked.connect(self._on_browse_clicked)
        self.btn_remove_selected.clicked.connect(self._on_remove_selected_clicked)
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        self.btn_output_browse.clicked.connect(self._on_output_browse_clicked)
        self.btn_start.clicked.connect(self._on_start_clicked)
        self.btn_queue.clicked.connect(self._on_queue_clicked)
        self.file_list.itemSelectionChanged.connect(self._on_file_selection_changed)
        self.file_list.files_dropped.connect(self._on_files_dropped)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        self.ensemble_checkbox.stateChanged.connect(self._on_ensemble_toggled)

    def _load_models(self):
        """Load available models into dropdown"""
        model_manager = self.ctx.model_manager()

        # Clear existing items to prevent duplicates
        self.model_combo.clear()

        for model_id, model_info in model_manager.available_models.items():
            # Format: "Description - Stems - Model Name" (with ⚠ for non-downloaded)
            # Example: "⚡ Fast karaoke creation - Vocals, Instrumental - MDX-Net Vocals"
            status = "⚠ " if not model_info.downloaded else ""

            # Get description (remove emoji and "stem" suffix for cleaner look)
            description = (
                model_info.description if hasattr(model_info, "description") else ""
            )

            # Get stem names
            if hasattr(model_info, "stem_names") and model_info.stem_names:
                stems_info = ", ".join(model_info.stem_names)
            else:
                stems_info = f"{model_info.stems} stems"

            # Combine: Description - Stems - Name
            text = f"{status}{description} - {stems_info} - {model_info.name}"
            self.model_combo.addItem(text, userData=model_id)

        # Select default model
        default_model = model_manager.get_default_model()
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == default_model:
                self.model_combo.setCurrentIndex(i)
                break

    @Slot(list)
    def _on_files_dropped(self, file_paths: List[Path]):
        """Handle dropped files from drag-and-drop"""
        for file_path in file_paths:
            self.add_file(file_path)

    def add_file(self, file_path: Path):
        """
        Add file to list with validation

        WHY: Validates format and readability before allowing selection
        """
        file_manager = self.ctx.file_manager()

        # Validate file
        is_valid, error_msg = file_manager.validate_audio_file(file_path)

        if not is_valid:
            QMessageBox.warning(
                self,
                self.ctx.translate("upload.error.title", "Invalid File"),
                f"{file_path.name}: {error_msg}",
            )
            return

        # Check if already in list
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.data(Qt.UserRole) == file_path:
                self.ctx.logger().debug(f"File already in list: {file_path}")
                return

        # Get audio info for display
        info = file_manager.get_audio_info(file_path)
        duration_str = f"{info['duration']:.1f}s" if info else "?"

        # Add to list
        item = QListWidgetItem(f"{file_path.name} ({duration_str})")
        item.setData(Qt.UserRole, file_path)
        self.file_list.addItem(item)

        # Auto-select the newly added item
        self.file_list.setCurrentItem(item)

        self._update_button_states()
        self.ctx.logger().info(f"Added file: {file_path.name}")

    @Slot()
    def _on_browse_clicked(self):
        """Open file browser dialog"""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter("Audio Files (*.wav *.mp3 *.flac *.m4a *.ogg *.aac)")

        if file_dialog.exec():
            file_paths = file_dialog.selectedFiles()
            for file_path_str in file_paths:
                self.add_file(Path(file_path_str))

    @Slot()
    def _on_remove_selected_clicked(self):
        """Remove selected file(s) from list"""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return

        # Remove all selected items
        for item in selected_items:
            row = self.file_list.row(item)
            self.file_list.takeItem(row)

        # Clear waveform if no items remain or no selection
        if self.file_list.count() == 0 or not self.file_list.selectedItems():
            self.waveform_widget.clear()

        self._update_button_states()
        self.ctx.logger().info(f"Removed {len(selected_items)} file(s) from list")

    @Slot()
    def _on_clear_clicked(self):
        """Clear file list"""
        self.file_list.clear()
        self.waveform_widget.clear()
        self._update_button_states()

    @Slot()
    def _on_file_selection_changed(self):
        """Handle file selection change - load waveform for selected file"""
        selected_items = self.file_list.selectedItems()

        if selected_items:
            # Get selected file path
            file_path = selected_items[0].data(Qt.UserRole)
            self.waveform_widget.load_file(file_path)
        else:
            # No selection - hide waveform
            self.waveform_widget.clear()

        self._update_button_states()

    @Slot()
    def _on_output_browse_clicked(self):
        """Select output directory"""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_path.setText(directory)

    @Slot()
    def _on_ensemble_toggled(self, state: int):
        """Handle ensemble mode checkbox toggle"""
        is_checked = state == Qt.CheckState.Checked.value

        # Refresh combo box contents based on mode
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        if is_checked:
            # Load Ensemble Configs
            for config_name, config_info in ENSEMBLE_CONFIGS.items():
                display_name = f"{config_info['name']} - {config_info['description']}"
                self.model_combo.addItem(display_name, userData=config_name)
        else:
            # Load Single Models (same format as _load_models)
            model_manager = self.ctx.model_manager()
            for model_id, model_info in model_manager.available_models.items():
                status = "⚠ " if not model_info.downloaded else ""
                description = (
                    model_info.description if hasattr(model_info, "description") else ""
                )

                if hasattr(model_info, "stem_names") and model_info.stem_names:
                    stems_info = ", ".join(model_info.stem_names)
                else:
                    stems_info = f"{model_info.stems} stems"

                text = f"{status}{description} - {stems_info} - {model_info.name}"
                self.model_combo.addItem(text, userData=model_id)

            # Select default model
            default_model = model_manager.get_default_model()
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i) == default_model:
                    self.model_combo.setCurrentIndex(i)
                    break

        self.model_combo.blockSignals(False)
        self._update_button_states()

    @Slot()
    def _on_model_changed(self, index: int):
        """Handle model selection change"""
        if index < 0:
            return

        # If in ensemble mode, no download check needed for config selection
        if self.ensemble_checkbox.isChecked():
            return

        model_id = self.model_combo.itemData(index)
        model_manager = self.ctx.model_manager()
        model_info = model_manager.get_model_info(model_id)

        if model_info and not model_info.downloaded:
            reply = QMessageBox.question(
                self,
                "Model Not Downloaded",
                f"Model '{model_info.name}' ({model_info.size_mb}MB) is not downloaded.\n\n"
                f"Download now? (This may take a few minutes)",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                self._download_model(model_id)

        # Update button states when model changes
        self._update_button_states()

    def _download_model(self, model_id: str):
        """
        Download model in background

        WHY: Model downloads can be large and slow; show progress to user
        """
        model_manager = self.ctx.model_manager()

        # Use a progress dialog that can always be closed; guard with try/finally
        from PySide6.QtWidgets import QProgressDialog

        progress = QProgressDialog(
            f"Downloading model {model_id}...", None, 0, 100, self
        )
        progress.setWindowTitle("Downloading Model")
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)  # We don't support cancel mid-download yet
        progress.setMinimumDuration(0)
        progress.show()

        def progress_callback(message: str, percent: int):
            progress.setLabelText(f"{message}\n{percent}%")
            progress.setValue(max(0, min(100, percent if percent >= 0 else 0)))
            QApplication.processEvents()

        try:
            # Download (blocking for simplicity - could be threaded)
            success = model_manager.download_model(model_id, progress_callback)
        finally:
            progress.close()

        if success:
            QMessageBox.information(self, "Success", "Model downloaded successfully!")
            # Reload model info to get updated download status
            model_manager._load_model_info()
            self._load_models()  # Refresh dropdown
        else:
            QMessageBox.critical(self, "Error", "Model download failed. Check logs.")

        # Update button states after download completes
        self._update_button_states()

    @Slot()
    def _on_start_clicked(self):
        """Start separation for selected file (via Global Queue)"""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return

        original_file = selected_items[0].data(Qt.UserRole)
        model_id = self.model_combo.currentData()

        output_dir = None
        if self.output_path.text().strip():
            output_dir = Path(self.output_path.text())

        # Check if ensemble mode is enabled
        use_ensemble = self.ensemble_checkbox.isChecked()
        ensemble_config = None
        if use_ensemble:
            ensemble_config = (
                self.model_combo.currentData()
            )  # Get config from same combo
            self.ctx.logger().info(
                f"Queueing ensemble separation: {original_file.name} with config {ensemble_config}"
            )
        else:
            self.ctx.logger().info(
                f"Queueing separation: {original_file.name} with model {model_id}"
            )

        # Create trimmed file if trimming is applied
        file_to_process = self._create_trimmed_file(original_file)

        # Add to queue
        self.file_queued.emit(file_to_process, model_id, use_ensemble, ensemble_config)

        # Notify user via QueueDrawer (auto-shows)
        # if self.window().statusBar():
        #      self.window().statusBar().showMessage(f"Added to queue and started: {file_to_process.name}", 5000)

        # Start queue immediately
        self.start_queue_requested.emit()

    @Slot()
    def _on_queue_clicked(self):
        """Add selected file to queue"""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return

        original_file = selected_items[0].data(Qt.UserRole)
        model_id = self.model_combo.currentData()

        # Get ensemble settings
        use_ensemble = self.ensemble_checkbox.isChecked()
        ensemble_config = self.model_combo.currentData() if use_ensemble else ""

        # Create trimmed file if trimming is applied
        mode_desc = (
            f"ensemble ({ensemble_config})" if use_ensemble else f"model ({model_id})"
        )
        self.ctx.logger().info(f"Queueing file: {original_file.name} with {mode_desc}")
        file_to_queue = self._create_trimmed_file(original_file)
        self.ctx.logger().info(f"File queued: {file_to_queue.name}")

        # Show user feedback via QueueDrawer (auto-shows)
        # if self.window().statusBar():
        #    self.window().statusBar().showMessage(f"Added to queue: {file_to_queue.name}", 5000)

        self.file_queued.emit(file_to_queue, model_id, use_ensemble, ensemble_config)

    def _create_trimmed_file(self, original_file: Path) -> Optional[Path]:
        """
        Create a trimmed copy of audio file based on waveform widget trim settings

        Args:
            original_file: Path to original audio file

        Returns:
            Path to trimmed file, or None if trimming not needed or failed

        WHY: Allows users to trim audio before separation without modifying original
        """
        # Check if waveform widget is visible and has trim data
        is_visible = self.waveform_widget.isVisible()
        self.ctx.logger().debug(f"Waveform widget visible: {is_visible}")

        if not is_visible:
            self.ctx.logger().info("Waveform not visible, using original file")
            return original_file

        start_sec, end_sec = self.waveform_widget.get_trim_range()
        duration = self.waveform_widget.duration

        self.ctx.logger().debug(
            f"Trim range: {start_sec:.2f}s to {end_sec:.2f}s (duration: {duration:.2f}s)"
        )

        # Check if any trimming is actually applied
        if start_sec <= 0.01 and end_sec >= (duration - 0.01):
            self.ctx.logger().info("No trimming applied, using original file")
            return original_file

        try:
            self.ctx.logger().info(
                f"Creating trimmed file: {start_sec:.2f}s to {end_sec:.2f}s"
            )

            # Read original audio
            audio_data, sample_rate = sf.read(original_file, dtype="float32")

            # Calculate sample indices
            start_sample = int(start_sec * sample_rate)
            end_sample = int(end_sec * sample_rate)

            # Trim audio data
            if audio_data.ndim == 1:
                # Mono
                trimmed_data = audio_data[start_sample:end_sample]
            else:
                # Stereo/multi-channel
                trimmed_data = audio_data[start_sample:end_sample, :]

            # Create output path with "_trimmed" suffix
            output_file = (
                original_file.parent
                / f"{original_file.stem}_trimmed{original_file.suffix}"
            )

            # Write trimmed audio
            sf.write(output_file, trimmed_data, sample_rate)

            self.ctx.logger().info(
                f"✓ Created trimmed file: {output_file.name} ({trimmed_data.shape[0] / sample_rate:.2f}s)"
            )
            self.ctx.logger().info(
                f"  Original: {original_file.name} → Trimmed: {output_file.name}"
            )
            return output_file

        except Exception as e:
            self.ctx.logger().error(
                f"Failed to create trimmed file: {e}", exc_info=True
            )
            QMessageBox.warning(
                self,
                "Trimming Failed",
                f"Could not create trimmed file. Using original file instead.\n\nError: {e}",
            )
            return original_file

    def _update_button_states(self):
        """Update button enabled states based on selection"""
        has_files = self.file_list.count() > 0
        has_selection = len(self.file_list.selectedItems()) > 0

        # Check if selected model is downloaded
        model_downloaded = False
        is_ensemble_mode = self.ensemble_checkbox.isChecked()

        if is_ensemble_mode:
            # Ensemble mode: configs don't need download check, just need selection
            model_downloaded = self.model_combo.currentIndex() >= 0
        elif self.model_combo.currentIndex() >= 0:
            # Single model mode: check if model is downloaded
            model_id = self.model_combo.currentData()
            if model_id:
                model_info = self.ctx.model_manager().get_model_info(model_id)
                model_downloaded = model_info.downloaded if model_info else False

        self.btn_remove_selected.setEnabled(has_selection)
        self.btn_clear.setEnabled(has_files)
        # Enable start if model/config is available (queue will handle processing state)
        self.btn_start.setEnabled(has_selection and model_downloaded)
        self.btn_queue.setEnabled(has_selection and model_downloaded)

    def apply_translations(self):
        """
        Apply current language translations

        WHY: Called when language changes; updates all visible text
        """
        # Note: Translation keys would be defined in resources/translations/*.json
        # For now, using English defaults
        pass
