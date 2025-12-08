"""
BlackHole Auto-Installer für macOS System Audio Recording
"""

import subprocess
import platform
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

from config import BLACKHOLE_HOMEBREW_FORMULA, BLACKHOLE_DEVICE_NAME
from utils.logger import get_logger

logger = get_logger()


@dataclass
class BlackHoleStatus:
    """Status von BlackHole Installation"""

    installed: bool
    version: Optional[str] = None
    device_found: bool = False
    homebrew_available: bool = False
    error_message: Optional[str] = None


class BlackHoleInstaller:
    """Verwaltet BlackHole Installation auf macOS"""

    def __init__(self):
        self.logger = logger
        self.formula = BLACKHOLE_HOMEBREW_FORMULA
        self.device_name = BLACKHOLE_DEVICE_NAME

    def check_macos(self) -> bool:
        """
        Prüft ob macOS läuft

        Returns:
            True wenn macOS
        """
        return platform.system() == "Darwin"

    def check_homebrew_installed(self) -> bool:
        """
        Prüft ob Homebrew installiert ist

        Returns:
            True wenn Homebrew verfügbar
        """
        try:
            result = subprocess.run(
                ["brew", "--version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def check_blackhole_installed(self) -> Tuple[bool, Optional[str]]:
        """
        Prüft ob BlackHole via Homebrew installiert ist

        Returns:
            (installed, version) Tuple
        """
        if not self.check_homebrew_installed():
            return False, None

        try:
            # Check for cask installation
            result = subprocess.run(
                ["brew", "list", "--cask", "--versions", self.formula],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                # Output format: "blackhole-2ch 0.6.1"
                version = result.stdout.strip().split()[-1]
                self.logger.info(f"BlackHole cask installed: {version}")
                return True, version

            # Fallback: check via pkgutil (system packages)
            pkg_result = subprocess.run(
                ["pkgutil", "--pkgs"], capture_output=True, text=True, timeout=10
            )

            if "BlackHole" in pkg_result.stdout:
                self.logger.info("BlackHole found via pkgutil")
                # Try to get version from brew cask info
                info_result = subprocess.run(
                    ["brew", "info", "--cask", self.formula],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                # Extract version from output
                for line in info_result.stdout.split("\n"):
                    if self.formula in line and ":" in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            version = parts[1]
                            return True, version
                return True, "installed"

            return False, None

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.logger.error(f"Error checking BlackHole: {e}")
            return False, None

    def check_blackhole_device(self) -> bool:
        """
        Prüft ob BlackHole Audio-Device existiert

        Returns:
            True wenn Device gefunden
        """
        try:
            # Versuche über Recorder
            from core.recorder import get_recorder

            recorder = get_recorder()
            device = recorder.find_blackhole_device()

            return device is not None

        except Exception as e:
            self.logger.debug(f"Could not check BlackHole device: {e}")
            return False

    def get_status(self) -> BlackHoleStatus:
        """
        Gibt vollständigen BlackHole-Status zurück

        Returns:
            BlackHoleStatus
        """
        if not self.check_macos():
            return BlackHoleStatus(
                installed=False,
                homebrew_available=False,
                error_message="Not running on macOS",
            )

        homebrew_available = self.check_homebrew_installed()

        if not homebrew_available:
            return BlackHoleStatus(
                installed=False,
                homebrew_available=False,
                error_message="Homebrew not installed",
            )

        installed, version = self.check_blackhole_installed()
        device_found = self.check_blackhole_device() if installed else False

        return BlackHoleStatus(
            installed=installed,
            version=version,
            device_found=device_found,
            homebrew_available=homebrew_available,
        )

    def install_blackhole(
        self, progress_callback: Optional[callable] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Installiert BlackHole via Homebrew

        Args:
            progress_callback: Callback für Progress-Updates

        Returns:
            (success, error_message) Tuple
        """
        if not self.check_macos():
            return False, "Not running on macOS"

        if not self.check_homebrew_installed():
            return False, "Homebrew not installed. Install from https://brew.sh"

        # Check ob bereits installiert
        installed, version = self.check_blackhole_installed()
        if installed:
            self.logger.info(f"BlackHole already installed: {version}")
            return True, None

        self.logger.info("Installing BlackHole via Homebrew...")

        if progress_callback:
            progress_callback("Installing BlackHole via Homebrew...")

        try:
            # brew install blackhole-2ch
            result = subprocess.run(
                ["brew", "install", self.formula],
                capture_output=True,
                text=True,
                timeout=300,  # 5 Minuten Timeout
            )

            if result.returncode == 0:
                self.logger.info("BlackHole installed successfully")

                if progress_callback:
                    progress_callback(
                        "BlackHole installed, restarting audio service..."
                    )

                # Restart CoreAudio service to load new driver
                try:
                    subprocess.run(
                        ["sudo", "killall", "coreaudiod"],
                        capture_output=True,
                        timeout=10,
                    )
                    self.logger.info("CoreAudio service restarted")
                except Exception as e:
                    self.logger.warning(f"Could not restart CoreAudio: {e}")

                # Wait a moment for audio service to restart
                import time

                time.sleep(2)

                if progress_callback:
                    progress_callback("Verifying installation...")

                # Verifiziere Installation
                installed, version = self.check_blackhole_installed()
                if installed:
                    if progress_callback:
                        progress_callback(
                            f"✓ BlackHole {version} installed successfully"
                        )
                    return True, None
                else:
                    # Installation war erfolgreich, aber Device noch nicht erkannt
                    # Das ist OK - Device wird nach App-Neustart verfügbar sein
                    self.logger.info("BlackHole installed but device not yet available")
                    return True, None

            else:
                error_msg = result.stderr.strip() or "Installation failed"
                self.logger.error(f"BlackHole installation failed: {error_msg}")
                return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "Installation timed out (>5 minutes)"

        except Exception as e:
            error_msg = f"Installation error: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg

    def uninstall_blackhole(self) -> Tuple[bool, Optional[str]]:
        """
        Deinstalliert BlackHole

        Returns:
            (success, error_message) Tuple
        """
        if not self.check_homebrew_installed():
            return False, "Homebrew not available"

        installed, _ = self.check_blackhole_installed()
        if not installed:
            return True, "BlackHole not installed"

        self.logger.info("Uninstalling BlackHole...")

        try:
            result = subprocess.run(
                ["brew", "uninstall", self.formula],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                self.logger.info("BlackHole uninstalled")
                return True, None
            else:
                error_msg = result.stderr.strip() or "Uninstall failed"
                return False, error_msg

        except Exception as e:
            return False, str(e)

    def get_setup_instructions(self) -> str:
        """
        Gibt Setup-Anleitung für Audio MIDI Setup zurück

        Returns:
            Mehrzeiliger Instruktionstext
        """
        instructions = """
BlackHole Setup Anleitung:

1. Öffne "Audio MIDI Setup" (im Programme/Dienstprogramme Ordner)

2. Erstelle ein "Multi-Output Device":
   - Klicke auf das "+" unten links
   - Wähle "Multi-Output Device erstellen"
   - Aktiviere BEIDE:
     ☑ BlackHole 2ch
     ☑ Dein Standard-Lautsprecher (z.B. "MacBook Pro Speakers")

3. Mache das Multi-Output Device zum Standard:
   - System-Einstellungen → Ton
   - Wähle das "Multi-Output Device" als Ausgabe

4. Fertig! System-Audio läuft jetzt durch BlackHole und deine Lautsprecher

TIPP: Um später wieder normal zu hören:
- Wähle einfach wieder deine normalen Lautsprecher in System-Einstellungen → Ton

Weitere Infos: https://github.com/ExistentialAudio/BlackHole/wiki/Multi-Output-Device
"""
        return instructions

    def open_audio_midi_setup(self) -> bool:
        """
        Öffnet Audio MIDI Setup App

        Returns:
            True wenn erfolgreich
        """
        if not self.check_macos():
            return False

        try:
            subprocess.Popen(
                ["open", "/System/Applications/Utilities/Audio MIDI Setup.app"]
            )
            self.logger.info("Opened Audio MIDI Setup")
            return True
        except Exception as e:
            self.logger.error(f"Could not open Audio MIDI Setup: {e}")
            return False


# Globale Instanz
_installer: Optional[BlackHoleInstaller] = None


def get_blackhole_installer() -> BlackHoleInstaller:
    """Gibt die globale BlackHoleInstaller-Instanz zurück"""
    global _installer
    if _installer is None:
        _installer = BlackHoleInstaller()
    return _installer


if __name__ == "__main__":
    # Test
    installer = BlackHoleInstaller()

    print("=== BlackHole Installer Test ===")
    print(f"Running on macOS: {installer.check_macos()}")
    print(f"Homebrew installed: {installer.check_homebrew_installed()}")

    status = installer.get_status()
    print(f"\nBlackHole Status:")
    print(f"  - Installed: {status.installed}")
    if status.version:
        print(f"  - Version: {status.version}")
    print(f"  - Device found: {status.device_found}")
    print(f"  - Homebrew available: {status.homebrew_available}")

    if status.error_message:
        print(f"  - Error: {status.error_message}")

    if not status.installed:
        print("\nInstall with:")
        print("  brew install blackhole-2ch")
        print("\nOr use installer.install_blackhole()")

    if status.installed and not status.device_found:
        print("\n" + installer.get_setup_instructions())
