# Loop Export Integration Guide

## Overview

This document describes how to integrate the Loop Export feature into the Player widget.

## Integration Steps

### 1. Import the Dialog

Add to `ui/widgets/player_widget.py` imports:

```python
from ui.dialogs import LoopExportDialog
from core.sampler_export import export_sampler_loops, detect_audio_bpm
```

### 2. Add "Export Loops" Button

In the `_setup_ui()` method, after the existing `btn_export` button:

```python
# Add after line ~382 (after self.btn_export)
self.btn_export_loops = QPushButton("🔁 Export Loops")
self.btn_export_loops.setEnabled(False)
self.btn_export_loops.setToolTip("Export as musical loops for samplers (2/4/8 bars)")

# Add button to layout
buttons_layout.addWidget(self.btn_export_loops)
```

### 3. Connect Signal

In the `_connect_signals()` method:

```python
# Add after line ~408 (after self.btn_export.clicked.connect)
self.btn_export_loops.clicked.connect(self._on_export_loops)
```

### 4. Enable/Disable Button

Update the button enable/disable logic wherever `btn_export` is enabled/disabled:

```python
# Example: In _on_files_dropped() after loading stems successfully
self.btn_export_loops.setEnabled(True)  # Line ~643

# Example: In clear_stems()
self.btn_export_loops.setEnabled(False)  # Line ~553
```

### 5. Implement Export Function

Add this method to the `PlayerWidget` class (around line ~900):

```python
@Slot()
def _on_export_loops(self):
    """Export audio as sampler loops with BPM-based bar lengths"""
    if not self.stem_files:
        return

    try:
        # Get mixed audio for BPM detection
        mixed_audio = self.player.get_mixed_audio()
        if mixed_audio is None or len(mixed_audio) == 0:
            QMessageBox.warning(
                self,
                "Export Failed",
                "Unable to get audio for export. Please try loading stems again."
            )
            return

        # Detect BPM
        from core.sampler_export import detect_audio_bpm
        detected_bpm, bpm_message = detect_audio_bpm(
            Path(list(self.stem_files.values())[0])  # Use first stem file
        )

        # Calculate duration
        duration_seconds = self.player.duration_samples / self.player.sample_rate if self.player.sample_rate > 0 else 0.0

        # Show loop export dialog
        dialog = LoopExportDialog(
            detected_bpm=detected_bpm,
            duration_seconds=duration_seconds,
            parent=self
        )

        if dialog.exec() != LoopExportDialog.Accepted:
            return

        # Get settings from dialog
        settings = dialog.get_settings()

        # Ask user for output directory
        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory for Loop Export"
        )

        if not output_dir:
            return

        output_path = Path(output_dir)

        # Create temporary mixed file for export
        # (sampler_export works on file paths, not in-memory audio)
        import tempfile
        import soundfile as sf

        with tempfile.NamedTemporaryFile(
            suffix='.wav',
            delete=False,
            dir=str(Path(output_dir).parent)  # Same drive for faster operations
        ) as temp_file:
            temp_path = Path(temp_file.name)

            try:
                # Export current mix to temporary file
                # Use player's current sample rate
                sf.write(
                    str(temp_path),
                    mixed_audio,
                    self.player.sample_rate,
                    subtype='PCM_24'
                )

                # Perform loop export
                from core.sampler_export import export_sampler_loops

                # Progress dialog
                progress_dialog = QMessageBox(self)
                progress_dialog.setWindowTitle("Exporting Loops")
                progress_dialog.setText("Exporting sampler loops...")
                progress_dialog.setStandardButtons(QMessageBox.NoButton)
                progress_dialog.setModal(True)
                progress_dialog.show()

                # Export with progress callback
                def progress_callback(message: str, percent: int):
                    progress_dialog.setText(f"Exporting sampler loops...\n\n{message} ({percent}%)")
                    # Process events to update UI
                    from PySide6.QtWidgets import QApplication
                    QApplication.processEvents()

                result = export_sampler_loops(
                    input_path=temp_path,
                    output_dir=output_path,
                    bpm=settings.bpm,
                    bars=settings.bars,
                    sample_rate=settings.sample_rate,
                    bit_depth=settings.bit_depth,
                    channels=settings.channels,
                    file_format=settings.file_format,
                    progress_callback=progress_callback
                )

                # Close progress dialog
                progress_dialog.close()

                # Show result
                if result.success:
                    warning_text = ""
                    if result.warning_messages:
                        warning_text = "\n\nWarnings:\n" + "\n".join(f"• {w}" for w in result.warning_messages)

                    QMessageBox.information(
                        self,
                        "Export Successful",
                        f"Exported {result.chunk_count} loop file(s) to:\n{output_path}\n\n"
                        f"Format: {settings.file_format}, {settings.bit_depth} bit, "
                        f"{'Stereo' if settings.channels == 2 else 'Mono'}\n"
                        f"Loop length: {settings.bars} bars at {settings.bpm} BPM"
                        f"{warning_text}"
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Export Failed",
                        f"Loop export failed:\n{result.error_message}"
                    )

            finally:
                # Clean up temporary file
                try:
                    temp_path.unlink()
                except Exception as e:
                    self.ctx.logger().warning(f"Failed to delete temp file {temp_path}: {e}")

    except Exception as e:
        self.ctx.logger().error(f"Loop export error: {e}", exc_info=True)
        QMessageBox.critical(
            self,
            "Export Failed",
            f"An error occurred during loop export:\n{str(e)}"
        )
```

## Alternative: Simplified Integration

If the full implementation is too complex, you can create a simpler version that:

1. Only exports from loaded audio files (not the mixed buffer)
2. Uses the first loaded stem file for BPM detection
3. Exports each stem separately as loops

## Testing the Integration

1. Load stems into the player
2. Click "Export Loops" button
3. Verify BPM detection shows reasonable value
4. Select bar length (2/4/8 bars)
5. Configure format/sample rate/bit depth
6. Verify preview shows correct number of chunks
7. Select output directory
8. Verify files are created with correct naming: `<name>_<BPM>_<bars>t_part<NN>.<ext>`

## Troubleshooting

### "No audio for export"
- Ensure stems are properly loaded before export
- Check that `player.get_mixed_audio()` returns valid data

### BPM Detection Fails
- Fallback to 120 BPM is automatic
- User can manually adjust BPM in the dialog

### Export Fails
- Check file permissions on output directory
- Check disk space
- Review error messages in log file

## Future Enhancements

See `core/sampler_export.py` docstring for `alignToTempoGrid` feature concept.
This would allow automatic detection of loop start points within arbitrary audio.
