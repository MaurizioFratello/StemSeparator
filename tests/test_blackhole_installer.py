"""
Unit Tests für BlackHole Installer
"""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from core.blackhole_installer import (
    BlackHoleInstaller,
    BlackHoleStatus,
    get_blackhole_installer,
)


@pytest.mark.unit
class TestBlackHoleStatus:
    """Tests für BlackHoleStatus Dataclass"""

    def test_status_creation_minimal(self):
        """Teste BlackHoleStatus Erstellung (minimal)"""
        status = BlackHoleStatus(installed=False)

        assert status.installed is False
        assert status.version is None
        assert status.device_found is False
        assert status.homebrew_available is False
        assert status.error_message is None

    def test_status_creation_full(self):
        """Teste BlackHoleStatus Erstellung (alle Felder)"""
        status = BlackHoleStatus(
            installed=True,
            version="0.4.0",
            device_found=True,
            homebrew_available=True,
            error_message=None,
        )

        assert status.installed is True
        assert status.version == "0.4.0"
        assert status.device_found is True
        assert status.homebrew_available is True
        assert status.error_message is None

    def test_status_with_error(self):
        """Teste BlackHoleStatus mit Error Message"""
        status = BlackHoleStatus(
            installed=False, error_message="Homebrew not installed"
        )

        assert status.installed is False
        assert status.error_message == "Homebrew not installed"


@pytest.mark.unit
class TestBlackHoleInstaller:
    """Tests für BlackHoleInstaller"""

    def test_initialization(self):
        """Teste Installer Initialisierung"""
        installer = BlackHoleInstaller()

        assert installer.formula == "blackhole-2ch"
        assert installer.device_name == "BlackHole 2ch"
        assert installer.logger is not None

    @patch("core.blackhole_installer.platform.system")
    def test_check_macos_true(self, mock_system):
        """Teste check_macos() auf macOS"""
        mock_system.return_value = "Darwin"

        installer = BlackHoleInstaller()
        assert installer.check_macos() is True

    @patch("core.blackhole_installer.platform.system")
    def test_check_macos_false(self, mock_system):
        """Teste check_macos() auf anderen Systemen"""
        mock_system.return_value = "Linux"

        installer = BlackHoleInstaller()
        assert installer.check_macos() is False

    @patch("subprocess.run")
    def test_check_homebrew_installed_true(self, mock_run):
        """Teste check_homebrew_installed() wenn verfügbar"""
        mock_run.return_value = Mock(returncode=0)

        installer = BlackHoleInstaller()
        assert installer.check_homebrew_installed() is True

        mock_run.assert_called_once_with(
            ["brew", "--version"], capture_output=True, text=True, timeout=5
        )

    @patch("subprocess.run")
    def test_check_homebrew_installed_false(self, mock_run):
        """Teste check_homebrew_installed() wenn nicht verfügbar"""
        mock_run.side_effect = FileNotFoundError()

        installer = BlackHoleInstaller()
        assert installer.check_homebrew_installed() is False

    @patch("subprocess.run")
    def test_check_homebrew_timeout(self, mock_run):
        """Teste check_homebrew_installed() bei Timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired("brew", 5)

        installer = BlackHoleInstaller()
        assert installer.check_homebrew_installed() is False

    @patch("subprocess.run")
    def test_check_blackhole_installed_true(self, mock_run):
        """Teste check_blackhole_installed() wenn installiert"""
        # Mock Homebrew check
        mock_run.side_effect = [
            Mock(returncode=0),  # brew --version
            Mock(returncode=0, stdout="blackhole-2ch 0.4.0\n"),  # brew list --versions
        ]

        installer = BlackHoleInstaller()
        installed, version = installer.check_blackhole_installed()

        assert installed is True
        assert version == "0.4.0"

    @patch("subprocess.run")
    def test_check_blackhole_installed_false(self, mock_run):
        """Teste check_blackhole_installed() wenn nicht installiert"""
        # Mock Homebrew check
        mock_run.side_effect = [
            Mock(returncode=0),  # brew --version
            Mock(returncode=1, stdout=""),  # brew list --versions
        ]

        installer = BlackHoleInstaller()
        installed, version = installer.check_blackhole_installed()

        assert installed is False
        assert version is None

    @patch("subprocess.run")
    def test_check_blackhole_no_homebrew(self, mock_run):
        """Teste check_blackhole_installed() ohne Homebrew"""
        mock_run.side_effect = FileNotFoundError()

        installer = BlackHoleInstaller()
        installed, version = installer.check_blackhole_installed()

        assert installed is False
        assert version is None

    @patch("subprocess.run")
    def test_check_blackhole_timeout(self, mock_run):
        """Teste check_blackhole_installed() bei Timeout"""
        mock_run.side_effect = [
            Mock(returncode=0),  # brew --version
            subprocess.TimeoutExpired("brew list", 10),
        ]

        installer = BlackHoleInstaller()
        installed, version = installer.check_blackhole_installed()

        assert installed is False
        assert version is None

    def test_check_blackhole_device_found(self):
        """Teste check_blackhole_device() wenn Device gefunden"""
        with patch("core.recorder.get_recorder") as mock_get_recorder:
            mock_recorder = Mock()
            mock_device = Mock()
            mock_device.name = "BlackHole 2ch"
            mock_recorder.find_blackhole_device.return_value = mock_device
            mock_get_recorder.return_value = mock_recorder

            installer = BlackHoleInstaller()
            assert installer.check_blackhole_device() is True

    def test_check_blackhole_device_not_found(self):
        """Teste check_blackhole_device() wenn Device nicht gefunden"""
        with patch("core.recorder.get_recorder") as mock_get_recorder:
            mock_recorder = Mock()
            mock_recorder.find_blackhole_device.return_value = None
            mock_get_recorder.return_value = mock_recorder

            installer = BlackHoleInstaller()
            assert installer.check_blackhole_device() is False

    def test_check_blackhole_device_error(self):
        """Teste check_blackhole_device() bei Error"""
        with patch("core.recorder.get_recorder") as mock_get_recorder:
            mock_get_recorder.side_effect = Exception("Import error")

            installer = BlackHoleInstaller()
            assert installer.check_blackhole_device() is False

    @patch("core.blackhole_installer.platform.system")
    def test_get_status_not_macos(self, mock_system):
        """Teste get_status() auf nicht-macOS"""
        mock_system.return_value = "Windows"

        installer = BlackHoleInstaller()
        status = installer.get_status()

        assert status.installed is False
        assert status.homebrew_available is False
        assert status.error_message == "Not running on macOS"

    @patch("subprocess.run")
    @patch("core.blackhole_installer.platform.system")
    def test_get_status_no_homebrew(self, mock_system, mock_run):
        """Teste get_status() ohne Homebrew"""
        mock_system.return_value = "Darwin"
        mock_run.side_effect = FileNotFoundError()

        installer = BlackHoleInstaller()
        status = installer.get_status()

        assert status.installed is False
        assert status.homebrew_available is False
        assert status.error_message == "Homebrew not installed"

    @patch("subprocess.run")
    @patch("core.blackhole_installer.platform.system")
    def test_get_status_installed_with_device(self, mock_system, mock_run):
        """Teste get_status() wenn installiert und Device gefunden"""
        mock_system.return_value = "Darwin"
        mock_run.side_effect = [
            Mock(returncode=0),  # brew --version (in get_status -> check_homebrew)
            Mock(
                returncode=0
            ),  # brew --version (in check_blackhole_installed -> check_homebrew)
            Mock(returncode=0, stdout="blackhole-2ch 0.4.0\n"),  # brew list
        ]

        with patch("core.recorder.get_recorder") as mock_get_recorder:
            mock_recorder = Mock()
            mock_recorder.find_blackhole_device.return_value = Mock()
            mock_get_recorder.return_value = mock_recorder

            installer = BlackHoleInstaller()
            status = installer.get_status()

            assert status.installed is True
            assert status.version == "0.4.0"
            assert status.device_found is True
            assert status.homebrew_available is True
            assert status.error_message is None

    @patch("subprocess.run")
    @patch("core.blackhole_installer.platform.system")
    def test_get_status_installed_no_device(self, mock_system, mock_run):
        """Teste get_status() wenn installiert aber kein Device"""
        mock_system.return_value = "Darwin"
        mock_run.side_effect = [
            Mock(returncode=0),  # brew --version (in get_status -> check_homebrew)
            Mock(
                returncode=0
            ),  # brew --version (in check_blackhole_installed -> check_homebrew)
            Mock(returncode=0, stdout="blackhole-2ch 0.4.0\n"),  # brew list
        ]

        with patch.object(
            BlackHoleInstaller, "check_blackhole_device", return_value=False
        ):
            installer = BlackHoleInstaller()
            status = installer.get_status()

            assert status.installed is True
            assert status.version == "0.4.0"
            assert status.device_found is False

    @patch("core.blackhole_installer.platform.system")
    def test_install_blackhole_not_macos(self, mock_system):
        """Teste install_blackhole() auf nicht-macOS"""
        mock_system.return_value = "Linux"

        installer = BlackHoleInstaller()
        success, error = installer.install_blackhole()

        assert success is False
        assert error == "Not running on macOS"

    @patch("subprocess.run")
    @patch("core.blackhole_installer.platform.system")
    def test_install_blackhole_no_homebrew(self, mock_system, mock_run):
        """Teste install_blackhole() ohne Homebrew"""
        mock_system.return_value = "Darwin"
        mock_run.side_effect = FileNotFoundError()

        installer = BlackHoleInstaller()
        success, error = installer.install_blackhole()

        assert success is False
        assert "Homebrew not installed" in error

    @patch("subprocess.run")
    @patch("core.blackhole_installer.platform.system")
    def test_install_blackhole_already_installed(self, mock_system, mock_run):
        """Teste install_blackhole() wenn bereits installiert"""
        mock_system.return_value = "Darwin"
        mock_run.side_effect = [
            Mock(
                returncode=0
            ),  # brew --version (in install_blackhole -> check_homebrew)
            Mock(
                returncode=0
            ),  # brew --version (in check_blackhole_installed -> check_homebrew)
            Mock(returncode=0, stdout="blackhole-2ch 0.4.0\n"),  # brew list
        ]

        installer = BlackHoleInstaller()
        success, error = installer.install_blackhole()

        assert success is True
        assert error is None

    @patch("subprocess.run")
    @patch("core.blackhole_installer.platform.system")
    def test_install_blackhole_success(self, mock_system, mock_run):
        """Teste install_blackhole() erfolgreich"""
        mock_system.return_value = "Darwin"
        mock_run.side_effect = [
            Mock(returncode=0),  # brew --version (in check_homebrew)
            Mock(returncode=0),  # brew --version (in check_blackhole)
            Mock(returncode=1, stdout=""),  # brew list (not installed)
            Mock(returncode=0),  # brew install
            Mock(returncode=0),  # brew --version (verify)
            Mock(returncode=0, stdout="blackhole-2ch 0.4.0\n"),  # brew list (verify)
        ]

        installer = BlackHoleInstaller()
        success, error = installer.install_blackhole()

        assert success is True
        assert error is None

    @patch("subprocess.run")
    @patch("core.blackhole_installer.platform.system")
    def test_install_blackhole_failure(self, mock_system, mock_run):
        """Teste install_blackhole() bei Fehler"""
        mock_system.return_value = "Darwin"
        mock_run.side_effect = [
            Mock(returncode=0),  # brew --version (check_homebrew)
            Mock(returncode=0),  # brew --version (check_blackhole)
            Mock(returncode=1, stdout=""),  # brew list (not installed)
            Mock(returncode=1, stderr="Installation failed"),  # brew install fails
        ]

        installer = BlackHoleInstaller()
        success, error = installer.install_blackhole()

        assert success is False
        assert "Installation failed" in error

    @patch("subprocess.run")
    @patch("core.blackhole_installer.platform.system")
    def test_install_blackhole_timeout(self, mock_system, mock_run):
        """Teste install_blackhole() bei Timeout"""
        mock_system.return_value = "Darwin"
        mock_run.side_effect = [
            Mock(returncode=0),  # brew --version (check_homebrew)
            Mock(returncode=0),  # brew --version (check_blackhole)
            Mock(returncode=1, stdout=""),  # brew list (not installed)
            subprocess.TimeoutExpired("brew install", 300),  # Install timeout
        ]

        installer = BlackHoleInstaller()
        success, error = installer.install_blackhole()

        assert success is False
        assert "timed out" in error.lower()

    @patch("subprocess.run")
    @patch("core.blackhole_installer.platform.system")
    def test_install_blackhole_with_callback(self, mock_system, mock_run):
        """Teste install_blackhole() mit Progress Callback"""
        mock_system.return_value = "Darwin"
        mock_run.side_effect = [
            Mock(returncode=0),  # brew --version
            Mock(returncode=0),  # brew --version
            Mock(returncode=1, stdout=""),  # brew list (not installed)
            Mock(returncode=0),  # brew install
            Mock(returncode=0),  # brew --version
            Mock(returncode=0, stdout="blackhole-2ch 0.4.0\n"),  # brew list
        ]

        callback_messages = []

        def progress_callback(msg):
            callback_messages.append(msg)

        installer = BlackHoleInstaller()
        success, error = installer.install_blackhole(
            progress_callback=progress_callback
        )

        assert success is True
        assert len(callback_messages) > 0
        assert any("Installing" in msg for msg in callback_messages)

    @patch("subprocess.run")
    def test_uninstall_blackhole_no_homebrew(self, mock_run):
        """Teste uninstall_blackhole() ohne Homebrew"""
        mock_run.side_effect = FileNotFoundError()

        installer = BlackHoleInstaller()
        success, error = installer.uninstall_blackhole()

        assert success is False
        assert "Homebrew not available" in error

    @patch("subprocess.run")
    def test_uninstall_blackhole_not_installed(self, mock_run):
        """Teste uninstall_blackhole() wenn nicht installiert"""
        mock_run.side_effect = [
            Mock(returncode=0),  # brew --version
            Mock(returncode=0),  # brew --version
            Mock(returncode=1, stdout=""),  # brew list (not found)
        ]

        installer = BlackHoleInstaller()
        success, error = installer.uninstall_blackhole()

        assert success is True
        assert "not installed" in error

    @patch("subprocess.run")
    def test_uninstall_blackhole_success(self, mock_run):
        """Teste uninstall_blackhole() erfolgreich"""
        mock_run.side_effect = [
            Mock(returncode=0),  # brew --version
            Mock(returncode=0),  # brew --version
            Mock(returncode=0, stdout="blackhole-2ch 0.4.0\n"),  # brew list
            Mock(returncode=0),  # brew uninstall
        ]

        installer = BlackHoleInstaller()
        success, error = installer.uninstall_blackhole()

        assert success is True
        assert error is None

    @patch("subprocess.run")
    def test_uninstall_blackhole_failure(self, mock_run):
        """Teste uninstall_blackhole() bei Fehler"""
        mock_run.side_effect = [
            Mock(returncode=0),  # brew --version
            Mock(returncode=0),  # brew --version
            Mock(returncode=0, stdout="blackhole-2ch 0.4.0\n"),  # brew list
            Mock(returncode=1, stderr="Uninstall failed"),  # brew uninstall fails
        ]

        installer = BlackHoleInstaller()
        success, error = installer.uninstall_blackhole()

        assert success is False
        assert "Uninstall failed" in error

    def test_get_setup_instructions(self):
        """Teste get_setup_instructions()"""
        installer = BlackHoleInstaller()
        instructions = installer.get_setup_instructions()

        assert isinstance(instructions, str)
        assert len(instructions) > 0
        assert "Audio MIDI Setup" in instructions
        assert "Multi-Output Device" in instructions
        assert "BlackHole" in instructions

    @patch("subprocess.Popen")
    @patch("core.blackhole_installer.platform.system")
    def test_open_audio_midi_setup_success(self, mock_system, mock_popen):
        """Teste open_audio_midi_setup() erfolgreich"""
        mock_system.return_value = "Darwin"

        installer = BlackHoleInstaller()
        result = installer.open_audio_midi_setup()

        assert result is True
        mock_popen.assert_called_once_with(
            ["open", "/System/Applications/Utilities/Audio MIDI Setup.app"]
        )

    @patch("core.blackhole_installer.platform.system")
    def test_open_audio_midi_setup_not_macos(self, mock_system):
        """Teste open_audio_midi_setup() auf nicht-macOS"""
        mock_system.return_value = "Windows"

        installer = BlackHoleInstaller()
        result = installer.open_audio_midi_setup()

        assert result is False

    @patch("subprocess.Popen")
    @patch("core.blackhole_installer.platform.system")
    def test_open_audio_midi_setup_error(self, mock_system, mock_popen):
        """Teste open_audio_midi_setup() bei Fehler"""
        mock_system.return_value = "Darwin"
        mock_popen.side_effect = Exception("Cannot open")

        installer = BlackHoleInstaller()
        result = installer.open_audio_midi_setup()

        assert result is False

    def test_singleton(self):
        """Teste get_blackhole_installer Singleton"""
        installer1 = get_blackhole_installer()
        installer2 = get_blackhole_installer()

        assert installer1 is installer2
        assert isinstance(installer1, BlackHoleInstaller)
