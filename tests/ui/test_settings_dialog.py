"""
Tests for SettingsDialog

PURPOSE: Verify settings configuration UI and persistence.
CONTEXT: Tests settings dialog with mocked settings manager.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from ui.widgets.settings_dialog import SettingsDialog
from ui.settings_manager import SettingsManager


@pytest.mark.unit
def test_settings_dialog_creation(qapp, reset_singletons):
    """Test that settings dialog can be created"""
    dialog = SettingsDialog()

    assert dialog is not None
    assert dialog.tabs is not None
    assert dialog.tabs.count() == 4  # General, Performance, Audio, Advanced


@pytest.mark.unit
def test_settings_dialog_has_tabs(qapp, reset_singletons):
    """Test that dialog has all expected tabs"""
    dialog = SettingsDialog()

    tab_names = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]

    assert "General" in tab_names
    assert "Performance" in tab_names
    assert "Audio" in tab_names
    assert "Advanced" in tab_names


@pytest.mark.unit
def test_settings_dialog_model_combo(qapp, reset_singletons):
    """Test model combo box"""
    dialog = SettingsDialog()

    # Should have models
    assert dialog.model_combo.count() > 0

    # Each model should have ID
    for i in range(dialog.model_combo.count()):
        model_id = dialog.model_combo.itemData(i)
        assert model_id is not None


@pytest.mark.unit
def test_settings_dialog_gpu_checkbox(qapp, reset_singletons):
    """Test GPU checkbox"""
    dialog = SettingsDialog()

    assert dialog.gpu_checkbox is not None
    # Checkbox state depends on current settings


@pytest.mark.unit
def test_settings_dialog_chunk_spinbox(qapp, reset_singletons):
    """Test chunk size spinbox"""
    dialog = SettingsDialog()

    assert dialog.chunk_spinbox is not None
    assert dialog.chunk_spinbox.minimum() == 60
    assert dialog.chunk_spinbox.maximum() == 600


@pytest.mark.unit
def test_settings_dialog_save_settings(qapp, reset_singletons):
    """Test saving settings"""
    with patch("ui.settings_manager.SettingsManager.save") as mock_save:
        mock_save.return_value = True

        with patch("PySide6.QtWidgets.QMessageBox.information"):
            dialog = SettingsDialog()

            # Change a setting
            dialog.gpu_checkbox.setChecked(True)

            # Save
            dialog._on_save()

            # Save should have been called
            mock_save.assert_called_once()


@pytest.mark.unit
def test_settings_dialog_reset_to_defaults(qapp, reset_singletons):
    """Test resetting settings to defaults"""
    with patch("ui.settings_manager.SettingsManager._load_defaults") as mock_defaults:
        with patch("PySide6.QtWidgets.QMessageBox.question") as mock_question:
            from PySide6.QtWidgets import QMessageBox

            mock_question.return_value = QMessageBox.Yes

            dialog = SettingsDialog()

            # Reset mock to ignore initialization call
            mock_defaults.reset_mock()

            # Reset
            dialog._on_reset()

            # Defaults should have been loaded
            mock_defaults.assert_called_once()


@pytest.mark.unit
def test_settings_dialog_browse_output_directory(qapp, reset_singletons, tmp_path):
    """Test browsing for output directory"""
    with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory") as mock_dialog:
        mock_dialog.return_value = str(tmp_path)

        dialog = SettingsDialog()

        # Browse
        dialog._on_browse_output()

        # Path should be set
        assert dialog.output_path.text() == str(tmp_path)


@pytest.mark.unit
def test_settings_dialog_cancel(qapp, reset_singletons):
    """Test cancelling settings dialog"""
    dialog = SettingsDialog()

    # Cancel should not save
    with patch("ui.settings_manager.SettingsManager.save") as mock_save:
        dialog.reject()

        # Save should not have been called
        mock_save.assert_not_called()


@pytest.mark.unit
def test_settings_dialog_signal_emission(qapp, reset_singletons):
    """Test that settings_changed signal is emitted on save"""
    with patch("ui.settings_manager.SettingsManager.save") as mock_save:
        mock_save.return_value = True

        dialog = SettingsDialog()

        # Connect signal spy
        signal_emitted = []
        dialog.settings_changed.connect(lambda: signal_emitted.append(True))

        with patch("PySide6.QtWidgets.QMessageBox.information"):
            dialog._on_save()

        # Signal should have been emitted
        assert len(signal_emitted) == 1
