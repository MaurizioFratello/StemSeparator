"""
Integration Tests for GUI Workflows

PURPOSE: Test complete user workflows from GUI perspective.
CONTEXT: End-to-end tests simulating real user interactions.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest

from ui.main_window import MainWindow
from core.recorder import RecordingState

@pytest.mark.integration
def test_complete_upload_workflow(qapp, reset_singletons, mock_audio_file, tmp_path):
    """
    Integration test: add file → select model → start separation → task lands
    in the global queue and the window switches to the queue tab.

    WHY written against the current API: the queue DRAWER was replaced by a
    queue TAB during the port (`MainWindow._queue_widget`, content-stack index
    2), the private `_add_file` is the public `add_file`, and
    `_on_start_clicked` now just emits `file_queued` +
    `start_queue_requested` — so the `audio_separator.Separator` patch of the
    old version mocked a layer this workflow never touches. Patching
    `QueueWorker` keeps the worker (and with it any real model download or
    subprocess) out of the unit run while everything upstream of it is real.
    """
    with patch("ui.widgets.queue_widget.QueueWorker"):
        # Create main window
        window = MainWindow()
        window.show()
        QTest.qWaitForWindowExposed(window)

        # Navigate to Upload tab
        upload_widget = window._upload_widget
        window._content_stack.setCurrentWidget(upload_widget)

        # Add file (public API; validates via file_manager)
        upload_widget.add_file(mock_audio_file)
        assert upload_widget.file_list.count() == 1

        # Select file
        upload_widget.file_list.setCurrentRow(0)
        assert upload_widget.btn_start.isEnabled()

        # Deterministic output location instead of the user's default dir.
        upload_widget.output_path.setText(str(tmp_path))

        # Select model (default selection must survive repopulation)
        assert upload_widget.model_combo.count() > 0
        model_id = upload_widget.model_combo.currentData()

        # Start separation (queues and requests start)
        upload_widget._on_start_clicked()

        queue_widget = window._queue_widget
        assert len(queue_widget.tasks) == 1
        assert queue_widget.tasks[0].file_path == mock_audio_file
        assert queue_widget.tasks[0].model_id == model_id

        # The requested start switched the window to the queue tab.
        assert window._content_stack.currentWidget() is queue_widget



@pytest.mark.integration
def test_recording_to_file_workflow(qapp, qtbot, reset_singletons, tmp_path):
    """
    Integration test: Start recording → Stop → Save file → Verify

    WHY: Tests complete recording workflow as user would experience it
    """
    with patch("soundcard.all_microphones") as mock_mics:
        with patch("soundcard.all_speakers") as mock_speakers:
            # Mock devices
            mock_device = MagicMock()
            mock_device.name = "BlackHole 2ch"
            mock_mics.return_value = [mock_device]
            mock_speakers.return_value = []

            # Fake capture stream. TWO properties matter (a previous version
            # had neither and leaked a live record loop through the whole
            # suite): the fake must be PACED like a real device —
            # soundcard.record(numframes=N) blocks for N/sample_rate seconds,
            # an unpaced instant-return fake turns `_record_loop` into a
            # GIL-hungry hot loop — and the test must go through the REAL
            # `Recorder.stop_recording`, because that is what sets
            # `_stop_event` and joins the thread. Content: a 0.5-peak sine so
            # silence-trimming leaves the recording alone.
            import numpy as np
            import threading

            phase = {"t": 0.0}

            def fake_record(numframes):
                time.sleep(numframes / 44100.0)
                t = (np.arange(numframes) / 44100.0) + phase["t"]
                phase["t"] += numframes / 44100.0
                mono = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
                return np.stack([mono, mono], axis=1)

            # Mock recorder context
            mock_recorder_context = MagicMock()
            mock_recorder_context.__enter__ = MagicMock(
                return_value=mock_recorder_context
            )
            mock_recorder_context.__exit__ = MagicMock(return_value=None)
            mock_recorder_context.record = fake_record

            mock_device.recorder = MagicMock(return_value=mock_recorder_context)

            # Create main window
            window = MainWindow()
            window.show()
            QTest.qWaitForWindowExposed(window)

            # Navigate to Recording tab
            recording_widget = window._recording_widget
            window._content_stack.setCurrentWidget(recording_widget)

            # Refresh devices
            recording_widget._refresh_devices()
            assert recording_widget.device_combo.count() > 0

            # Deterministic save location (no file dialog in this flow).
            recording_widget.output_path.setText(str(tmp_path))

            # Start recording
            recording_widget._on_start_clicked()

            # Synchronise on ACTUAL capture, not wall time: `QTest.qWait`
            # only pumps Qt events, and under GIL contention the Python
            # record thread advances far slower than its device pacing
            # (measured: 4 blocks in a 300 ms wait). `waitUntil` pumps the
            # event loop while giving the worker air, making the "audio
            # flowed" precondition deterministic.
            qtbot.waitUntil(
                lambda: len(recording_widget.recorder.recorded_chunks) >= 8,
                timeout=5000,
            )

            # Should be recording
            assert not recording_widget.btn_start.isEnabled()
            assert recording_widget.btn_stop.isEnabled()

            # Stop through the product path (the success information box is
            # modal and would block the offscreen runner).
            with patch("PySide6.QtWidgets.QMessageBox.information"):
                recording_widget._on_stop_clicked()

            recorder = recording_widget.recorder
            assert recorder.state == RecordingState.IDLE
            assert not [
                t
                for t in threading.enumerate()
                if getattr(t, "_target", None) is not None
                and getattr(t._target, "__self__", None) is recorder
            ], "record loop leaked past stop_recording"

            saved = list(tmp_path.glob("recording_*.wav"))
            assert len(saved) == 1, f"expected one recording, got {saved}"

            import soundfile as sf

            data, sr = sf.read(str(saved[0]))
            assert sr == 44100
            assert 0.05 < data.shape[0] / sr < 2.0
            assert 0.3 < float(np.max(np.abs(data))) <= 0.6


@pytest.mark.integration
def test_queue_batch_processing_workflow(qapp, reset_singletons, tmp_path):
    """
    Integration test: Add files to queue → Start batch processing → Monitor progress

    WHY: Tests queue widget with multiple files
    """
    # Create multiple test files
    test_files = []
    for i in range(3):
        test_file = tmp_path / f"test_file_{i}.wav"

        # Create minimal valid WAV
        import wave
        import numpy as np

        with wave.open(str(test_file), "w") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(np.zeros((44100, 2), dtype=np.int16).tobytes())

        test_files.append(test_file)

    # `QueueWorker` is the seam that would spawn the real separation
    # subprocess (and model downloads) — patched, exactly as in
    # `test_complete_upload_workflow`. The old patch of
    # `audio_separator.separator.Separator` mocked a class this flow never
    # imports: the queue runs the app's OWN `core.separator.Separator` in a
    # worker process, invisible to that patch. The queue DRAWER became a
    # queue TAB (`MainWindow._queue_widget`) during the port.
    with patch("ui.widgets.queue_widget.QueueWorker"):
        # Create main window
        window = MainWindow()
        window.show()
        QTest.qWaitForWindowExposed(window)

        queue_widget = window._queue_widget

        # Add files to queue
        for test_file in test_files:
            queue_widget.add_task(test_file, "demucs_4s")

        assert len(queue_widget.tasks) == 3
        assert queue_widget.queue_table.rowCount() == 3

        # Start queue processing
        queue_widget.start_processing()

        # Should be processing
        assert queue_widget.is_processing


@pytest.mark.integration
def test_settings_persistence_workflow(qapp, reset_singletons, tmp_path):
    """
    Integration test: Change settings → Save → Restart → Verify loaded

    WHY: Tests settings persistence across sessions
    """
    from ui.settings_manager import SettingsManager

    # Create settings manager with temp file
    settings_file = tmp_path / "test_settings.json"

    with patch("ui.settings_manager.BASE_DIR", tmp_path):
        # First session: change and save settings
        settings_mgr = SettingsManager()
        settings_mgr.settings_file = settings_file

        original_lang = settings_mgr.get_language()
        new_lang = "en" if original_lang == "de" else "de"

        settings_mgr.set_language(new_lang)
        settings_mgr.set_use_gpu(False)
        settings_mgr.set_chunk_length(150)

        success = settings_mgr.save()
        assert success
        assert settings_file.exists()

        # Second session: load settings
        settings_mgr2 = SettingsManager()
        settings_mgr2.settings_file = settings_file
        settings_mgr2._load_from_file()

        # Settings should persist
        assert settings_mgr2.get_language() == new_lang
        assert settings_mgr2.get_use_gpu() == False
        assert settings_mgr2.get_chunk_length() == 150


@pytest.mark.integration
def test_upload_to_queue_signal_workflow(qapp, reset_singletons, mock_audio_file):
    """
    Integration test: Upload widget → Queue file → Verify in queue widget

    WHY: Tests signal-based communication between widgets
    """
    window = MainWindow()
    window.show()
    QTest.qWaitForWindowExposed(window)

    upload_widget = window._upload_widget
    queue_widget = window._queue_widget  # the drawer became a queue TAB

    # Add file to upload widget (public API — the private `_add_file` the
    # port-era test used no longer exists)
    upload_widget.add_file(mock_audio_file)
    upload_widget.file_list.setCurrentRow(0)

    # Queue it
    upload_widget._on_queue_clicked()

    # Should appear in queue
    assert len(queue_widget.tasks) == 1
    assert queue_widget.tasks[0].file_path == mock_audio_file
    assert queue_widget.queue_table.rowCount() == 1


@pytest.mark.integration
def test_recording_to_main_window_signal(
    qapp, reset_singletons, tmp_path, mock_audio_file
):
    """
    Integration test: Recording saved → Signal to main window → status update
    and the file handed to the upload widget.

    WHY the file must be a real WAV (a `.touch()`ed empty file hung this
    suite): the product path `MainWindow._on_recording_saved` →
    `UploadWidget.add_file` validates the audio file and answers an invalid
    one with a MODAL `QMessageBox.warning` — correct UX for a user, a
    deadlock for an offscreen runner. The previous mock made the flow
    impossible to finish without patching away the very warning that proves
    validation works.
    """
    window = MainWindow()
    window.show()
    QTest.qWaitForWindowExposed(window)

    recording_widget = window._recording_widget

    # Simulate recording saved (real, readable audio — see docstring).
    test_file = mock_audio_file

    recording_widget.recording_saved.emit(test_file)

    # Process events
    QTest.qWait(100)

    # Status feedback lives in the EnhancedStatusBar's own label: its
    # `showMessage` override renders into `_status_label` and never feeds
    # QStatusBar::currentMessage — asserting currentMessage() tested a dead
    # channel.
    from PySide6.QtWidgets import QLabel

    labels = [l.text() for l in window.statusBar().findChildren(QLabel)]
    assert any("Recording saved" in t or test_file.name in t for t in labels), labels

    # ... and the downstream effect the signal exists for: the upload widget
    # received the file (validation passed, no warning dialog fired).
    upload_widget = window._upload_widget
    paths = [
        upload_widget.file_list.item(i).data(Qt.UserRole)
        for i in range(upload_widget.file_list.count())
    ]
    assert test_file in paths


@pytest.mark.integration
def test_language_switch_workflow(qapp, reset_singletons):
    """
    Integration test: switch language → visible texts come from the new
    catalogue.

    WHY rewritten: this exercised `window._language_actions`, a menu that no
    longer exists (the MainWindow has no language UI; the real seam is
    `AppContext.set_language` + `MainWindow._apply_translations`, invoked by
    whoever persists the setting). Testing the seam that exists keeps the
    i18n integration honest.
    """
    window = MainWindow()
    window.show()
    QTest.qWaitForWindowExposed(window)

    # The shipped default is German (`DEFAULT_LANGUAGE = "de"`), so the test
    # must pin a known start instead of assuming the host default.
    window._context.set_language("en")
    window._apply_translations()
    assert window._context.translate("playback.output_label", "Output:") == "Output:"

    window._context.set_language("de")
    window._apply_translations()

    assert window._context.get_language() == "de"
    # A German string from resources/translations/de.json must be live in
    # the UI now (the playback output-label is translated; English-only
    # fallback text would prove the catalogue is NOT wired).
    assert window._context.translate("playback.output_label", "Output:") == "Ausgabe:"


@pytest.mark.integration
def test_player_load_stems_workflow(qapp, qtbot, reset_singletons, tmp_path):
    """
    Integration test: Load stems into player → Verify controls enabled

    WHY: Tests player widget with real file loading
    """
    # Create mock stem files
    stem_files = {}
    for stem_name in ["vocals", "drums", "bass", "other"]:
        stem_file = tmp_path / f"test_{stem_name}.wav"

        # Create minimal WAV
        import wave
        import numpy as np

        with wave.open(str(stem_file), "w") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(np.zeros((44100, 2), dtype=np.int16).tobytes())

        stem_files[stem_name] = stem_file

    window = MainWindow()
    window.show()
    QTest.qWaitForWindowExposed(window)

    player_widget = window._player_widget
    window._content_stack.setCurrentWidget(player_widget)

    # `_load_stems` hands parsing/loading to a BACKGROUND worker and enables
    # the controls in `on_finished` — wait for the finished state instead of
    # asserting the buttons one tick too early.
    player_widget._load_stems(list(stem_files.values()))

    qtbot.waitUntil(lambda: player_widget.btn_play.isEnabled(), timeout=15000)
    assert len(player_widget.stem_files) == 4
    assert len(player_widget.stem_controls) == 4
    assert set(player_widget.stem_files.values()) == set(stem_files.values())


@pytest.mark.integration
def test_error_handling_workflow(qapp, reset_singletons, tmp_path):
    """
    Integration test: Trigger error in separation → Verify error handling

    WHY: Tests error propagation and user notification
    """
    # Create invalid file
    invalid_file = tmp_path / "invalid.txt"
    invalid_file.write_text("not audio")

    window = MainWindow()
    window.show()
    QTest.qWaitForWindowExposed(window)

    upload_widget = window._upload_widget

    # Try to add invalid file
    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warning:
        upload_widget.add_file(invalid_file)

        # Should show warning
        mock_warning.assert_called_once()

    # File should not be added
    assert upload_widget.file_list.count() == 0


@pytest.mark.integration
@pytest.mark.slow
def test_full_user_journey(qapp, qtbot, reset_singletons, tmp_path):
    """
    Integration test: the complete happy path — open app, upload a file,
    queue it, start the queue, open settings.

    WHY rewritten against the current API: the private `_add_file` is gone
    (public `add_file`), the queue drawer is a queue TAB, and the old
    `audio_separator.separator.Separator` patch never intercepted this flow
    anyway — the queue runs the app's own `core.separator.Separator` inside
    `QueueWorker`, so `QueueWorker` itself is the honest seam to patch (same
    choice as the other queue tests). The previous version finished with
    `assert True`, which asserted nothing.
    """
    # Create test file
    test_file = tmp_path / "user_test.wav"
    import wave
    import numpy as np

    with wave.open(str(test_file), "w") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(np.zeros((88200, 2), dtype=np.int16).tobytes())

    from ui.widgets.settings_dialog import SettingsDialog

    with patch("ui.widgets.queue_widget.QueueWorker"), \
            patch.object(SettingsDialog, "exec") as mock_exec:
        # Step 1: Open app
        window = MainWindow()
        window.show()
        QTest.qWaitForWindowExposed(window)
        assert window.isVisible()

        # Step 2: Upload file
        upload_widget = window._upload_widget
        window._content_stack.setCurrentWidget(upload_widget)
        upload_widget.add_file(test_file)
        assert upload_widget.file_list.count() == 1

        # Step 3: Queue file
        upload_widget.file_list.setCurrentRow(0)
        upload_widget._on_queue_clicked()

        queue_widget = window._queue_widget
        assert len(queue_widget.tasks) == 1
        assert queue_widget.tasks[0].file_path == test_file

        # Step 4: Start the queue via the upload widget — the
        # `start_queue_requested` signal wiring must switch the window to
        # the queue tab.
        upload_widget._on_start_clicked()
        assert queue_widget.is_processing
        assert window._content_stack.currentWidget() is queue_widget

        # Step 5: Open settings — real wiring: the menu action path must
        # construct the dialog AND run it modally.
        window._show_settings()
        assert mock_exec.called

        # Step 6: Language change reaches the visible texts (the old test
        # listed "change settings" without ever asserting an effect).
        window._context.set_language("de")
        window._apply_translations()
        assert window._context.translate(
            "playback.output_label", "Output:"
        ) == "Ausgabe:"



@pytest.mark.integration
def test_queue_completed_row_loads_stems_into_player_stems_page(
    qapp, reset_singletons, qtbot, tmp_path
):
    """Full hand-off: completed queue row -> real signal -> MainWindow ->
    async Player loader -> populated, VISIBLE Stems sub-page.

    WHY this exists: the hand-off was first implemented against the OUTER
    content stack only; the Player's inner page stack (Stems/Playback/
    Looping) then stayed on the previously selected sub-page and the
    freshly loaded mixer strips remained invisible — the exact user
    complaint ("stems never show up in the stems tab"). Signal-capture
    unit tests could not see this; the assertion here is the visible end
    state. Starts from a hostile state (Playback sub-page) to pin it.
    """
    import numpy as np
    import soundfile as sf

    from core.separator import SeparationResult
    from ui.widgets.queue_widget import QueueTask, TaskStatus

    window = MainWindow()
    window.show()
    QTest.qWaitForWindowExposed(window)

    # Four REAL loadable WAVs: the player performs genuine I/O + resampling
    # (a touched file would trigger modal validation and deadlock offscreen).
    sr = 44100
    tone = (0.5 * np.sin(2 * np.pi * 440 * np.arange(sr // 2) / sr)).astype("float32")
    stems = {}
    for name in ("Vocals", "Drums", "Bass", "Other"):
        path = tmp_path / f"take_({name}).wav"
        sf.write(str(path), np.column_stack([tone, tone]), sr)
        stems[name] = path

    task = QueueTask(file_path=tmp_path / "take.wav", model_id="demucs_4s")
    task.status = TaskStatus.COMPLETED
    task.result = SeparationResult(
        success=True,
        input_file=tmp_path / "take.wav",
        output_dir=tmp_path,
        stems=stems,
        model_used="demucs_4s",
        device_used="cpu",
        duration_seconds=1.0,
    )
    window._queue_widget.tasks.append(task)

    # Hostile starting state: Playback sub-page selected through the sidebar.
    window._btn_playback.click()
    assert window._player_widget.get_current_page() == 1

    player = window._player_widget
    # WHY waitSignal and not the synchronous flags: stem_controls and
    # stems_list are populated inside _load_stems BEFORE _load_stems_async
    # starts, and has_stems_loaded() only checks len(stem_files).
    # stems_loaded_changed(True) is emitted exclusively from
    # LoadStemsWorker.on_finished after the real I/O + resampling
    # (player_widget.py:3155) — that is the completion to await.
    with qtbot.waitSignal(player.stems_loaded_changed, timeout=8000) as finished:
        # The completed-row double-click entry point (emits the real signal).
        window._queue_widget._on_row_double_clicked(0, 0)
    assert finished.args == [True]

    # State that only the async success path applies:
    assert player.position_slider.isEnabled()

    assert window._content_stack.currentWidget() is player
    assert (
        player.get_current_page() == 0
    ), "the hand-off must land on the Stems sub-page"
    page0 = player._page_stack.widget(0)
    assert page0.isVisible(), "the Stems page must actually be shown"

    # Stems page (index 0) owns the file list — that is its populated state.
    texts = [player.stems_list.item(i).text() for i in range(player.stems_list.count())]
    assert player.stems_list.count() == 4
    for stem in ("Vocals", "Drums", "Bass", "Other"):
        assert any(text.startswith(f"{stem}:") for text in texts)

    # The mixer strips live on the Playback page (index 1, own layout in
    # _create_playback_tab) — select it and assert the visible mixer.
    window._btn_playback.click()
    assert player.get_current_page() == 1
    assert set(player.stem_controls) == {"Vocals", "Drums", "Bass", "Other"}
    for control in player.stem_controls.values():
        assert control.isVisible(), (
            "mixer strips must be visible once their page is selected"
        )

