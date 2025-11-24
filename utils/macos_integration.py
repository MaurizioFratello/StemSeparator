"""
macOS System Integration Utilities

PURPOSE: Provides deep integration with macOS-specific features and behaviors.
CONTEXT: Native macOS apps integrate with system services, conventions, and APIs.
         This module provides those integrations for Qt apps on macOS.
"""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QDesktopServices


class MacOSIntegration(QObject):
    """
    Integrate with macOS system features

    WHY: Makes the Qt app behave like a native macOS citizen by respecting
         system conventions, integrating with Finder, and using macOS APIs.
    """

    @staticmethod
    def is_macos() -> bool:
        """Check if running on macOS"""
        return platform.system() == "Darwin"

    @staticmethod
    def reveal_in_finder(file_path: Path) -> bool:
        """
        Reveal a file in Finder

        WHY: Native macOS apps use "Reveal in Finder" to show users where
             files are saved. This is more useful than just opening the folder.

        Args:
            file_path: Path to file to reveal

        Returns:
            True if successful, False otherwise
        """
        if not MacOSIntegration.is_macos():
            # Fallback: open containing folder on other platforms
            folder = file_path.parent if file_path.is_file() else file_path
            return QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

        try:
            # Use AppleScript to reveal file in Finder
            script = f'tell application "Finder" to reveal POSIX file "{file_path}"'
            subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                check=True
            )

            # Bring Finder to front
            subprocess.run(
                ['osascript', '-e', 'tell application "Finder" to activate'],
                capture_output=True,
                check=False  # Don't fail if this part doesn't work
            )

            return True

        except Exception:
            # Fallback to opening folder
            folder = file_path.parent if file_path.is_file() else file_path
            return QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    @staticmethod
    def open_with_default_app(file_path: Path) -> bool:
        """
        Open file with default application

        WHY: Uses macOS "open" command which respects file associations
             and Launch Services preferences.

        Args:
            file_path: Path to file to open

        Returns:
            True if successful, False otherwise
        """
        if not MacOSIntegration.is_macos():
            return QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path)))

        try:
            subprocess.run(
                ['open', str(file_path)],
                capture_output=True,
                check=True
            )
            return True
        except Exception:
            return False

    @staticmethod
    def get_macos_version() -> Optional[tuple[int, int, int]]:
        """
        Get macOS version as tuple (major, minor, patch)

        WHY: Different macOS versions support different features.
             This allows us to conditionally enable features.

        Returns:
            Tuple of (major, minor, patch) or None if not macOS

        Example:
            macOS 13.4.1 returns (13, 4, 1)
        """
        if not MacOSIntegration.is_macos():
            return None

        try:
            result = subprocess.run(
                ['sw_vers', '-productVersion'],
                capture_output=True,
                text=True,
                check=True
            )
            version_str = result.stdout.strip()
            parts = version_str.split('.')

            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0

            return (major, minor, patch)

        except Exception:
            return None

    @staticmethod
    def is_dark_mode() -> bool:
        """
        Check if macOS is in dark mode using system defaults

        WHY: More reliable than Qt palette detection for some cases

        Returns:
            True if dark mode is enabled
        """
        if not MacOSIntegration.is_macos():
            return True  # Default to dark

        try:
            result = subprocess.run(
                ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
                capture_output=True,
                text=True,
                check=False  # Will fail if not in dark mode
            )
            return 'Dark' in result.stdout
        except Exception:
            return False

    @staticmethod
    def supports_vibrancy() -> bool:
        """
        Check if current macOS version supports vibrancy effects

        WHY: Vibrancy was introduced in macOS Yosemite (10.10) and evolved
             significantly in Big Sur (11.0). This checks compatibility.

        Returns:
            True if vibrancy is supported
        """
        version = MacOSIntegration.get_macos_version()
        if version is None:
            return False

        # Vibrancy supported from macOS 10.10+
        major, _, _ = version
        return major >= 10

    @staticmethod
    def supports_big_sur_design() -> bool:
        """
        Check if macOS version supports Big Sur design language

        WHY: Big Sur (macOS 11.0) introduced significant design changes:
             rounded corners, updated iconography, new color system.

        Returns:
            True if Big Sur+ design is available
        """
        version = MacOSIntegration.get_macos_version()
        if version is None:
            return False

        major, _, _ = version
        return major >= 11

    @staticmethod
    def trash_file(file_path: Path) -> bool:
        """
        Move file to Trash (instead of permanent deletion)

        WHY: macOS users expect files to go to Trash, not be permanently deleted.
             This allows recovery if user changes their mind.

        Args:
            file_path: Path to file to trash

        Returns:
            True if successful, False otherwise
        """
        if not MacOSIntegration.is_macos():
            return False

        try:
            # Use osascript to move to trash
            script = f'''
            tell application "Finder"
                delete POSIX file "{file_path}"
            end tell
            '''
            subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                check=True
            )
            return True
        except Exception:
            return False

    @staticmethod
    def get_default_output_folder() -> Path:
        """
        Get default output folder following macOS conventions

        WHY: macOS apps typically save to ~/Documents or ~/Music for audio files.
             This respects user expectations.

        Returns:
            Path to appropriate default output folder
        """
        if not MacOSIntegration.is_macos():
            return Path.home() / "Documents"

        # For audio app, Music folder makes sense
        music_folder = Path.home() / "Music"
        if music_folder.exists():
            # Create app-specific subfolder
            app_folder = music_folder / "Stem Separator"
            app_folder.mkdir(exist_ok=True)
            return app_folder

        # Fallback to Documents
        documents = Path.home() / "Documents"
        app_folder = documents / "Stem Separator"
        app_folder.mkdir(exist_ok=True)
        return app_folder


def get_macos_integration() -> MacOSIntegration:
    """Get MacOSIntegration instance (for convenience)"""
    return MacOSIntegration
