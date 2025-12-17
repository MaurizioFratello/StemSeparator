"""
ScreenCaptureKit Audio Recorder Python Wrapper

This module provides a Python interface to the Swift ScreenCaptureKit tool
for recording system audio on macOS 13.0+ without requiring BlackHole.
"""

from __future__ import annotations

import subprocess
import platform
import sys
from pathlib import Path
from typing import Optional, Callable
import threading
import time
import numpy as np
import soundfile as sf
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger()


@dataclass
class ScreenCaptureInfo:
    """Information about ScreenCaptureKit availability"""

    available: bool
    version: str
    error: Optional[str] = None


class ScreenCaptureRecorder:
    """
    Python wrapper for the Swift ScreenCaptureKit audio recorder

    This provides an alternative to BlackHole for system audio recording
    on macOS 13.0+ (Ventura and later).
    """

    def __init__(self):
        self.logger = logger
        self._binary_path: Optional[Path] = None
        self._recording_process: Optional[subprocess.Popen] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._current_output_path: Optional[Path] = None
        self._start_time: Optional[float] = None

        # Find the screencapture-recorder binary
        self._find_binary()

    def _find_binary(self) -> bool:
        """
        Locate the screencapture-recorder binary

        Returns:
            True if binary found and executable
        """
        # Try multiple possible locations
        possible_paths = []

        # Development build locations
        possible_paths.extend(
            [
                Path(__file__).parent.parent
                / "packaging/screencapture_tool/.build/release/screencapture-recorder",
                Path(__file__).parent.parent
                / "packaging/screencapture_tool/.build/arm64-apple-macosx/release/screencapture-recorder",
                Path(__file__).parent.parent
                / "packaging/screencapture_tool/.build/x86_64-apple-macosx/release/screencapture-recorder",
            ]
        )

        # Packaged application locations (when using PyInstaller)
        if getattr(sys, "frozen", False):
            # PyInstaller bundle structure on macOS:
            # App.app/Contents/
            #   MacOS/StemSeparator (sys.executable)
            #   Frameworks/screencapture-recorder (our binary)
            #   Resources/ (sys._MEIPASS points here or to a temp extract dir)

            # Try relative to executable first (most reliable)
            if hasattr(sys, "executable") and sys.executable:
                exe_path = Path(sys.executable)
                if exe_path.exists():
                    # From MacOS/StemSeparator -> Contents/Frameworks/
                    bundle_frameworks = (
                        exe_path.parent.parent / "Frameworks" / "screencapture-recorder"
                    )
                    possible_paths.append(bundle_frameworks)

            # Try via sys._MEIPASS (extracted temp directory)
            if hasattr(sys, "_MEIPASS"):
                meipass = Path(sys._MEIPASS)
                # Check if MEIPASS is in the bundle or temp directory
                possible_paths.extend(
                    [
                        meipass / "screencapture-recorder",
                        meipass.parent / "Frameworks" / "screencapture-recorder",
                    ]
                )

                # If MEIPASS is a temp directory, try to find the bundle
                # by going up to find the app bundle structure
                current = meipass
                for _ in range(5):  # Limit search depth
                    parent = current.parent
                    if (
                        parent.name.endswith(".app")
                        or (parent / "Contents" / "Frameworks").exists()
                    ):
                        possible_paths.append(
                            parent
                            / "Contents"
                            / "Frameworks"
                            / "screencapture-recorder"
                        )
                        break
                    current = parent

        # System-wide installation
        possible_paths.append(Path("/usr/local/bin/screencapture-recorder"))

        # Try all paths
        for path in possible_paths:
            if path and path.exists() and path.is_file():
                # Verify it's actually executable
                import os

                if os.access(path, os.X_OK):
                    self._binary_path = path
                    self.logger.info(f"Found screencapture-recorder at: {path}")
                    return True
                else:
                    self.logger.warning(
                        f"Found screencapture-recorder but not executable: {path}"
                    )

        # Log all attempted paths for debugging
        self.logger.warning("screencapture-recorder binary not found. Searched paths:")
        for path in possible_paths:
            if path:
                self.logger.warning(f"  - {path} (exists: {path.exists()})")

        return False

    def is_available(self) -> ScreenCaptureInfo:
        """
        Check if ScreenCaptureKit is available on this system

        Returns:
            ScreenCaptureInfo with availability status
        """
        # Check macOS version first
        if platform.system() != "Darwin":
            return ScreenCaptureInfo(
                available=False,
                version="N/A",
                error="ScreenCaptureKit only available on macOS",
            )

        # Parse macOS version
        macos_version = platform.mac_ver()[0]
        try:
            major, minor = map(int, macos_version.split(".")[:2])
            if major < 13:  # macOS 13.0 (Ventura) required
                return ScreenCaptureInfo(
                    available=False,
                    version=macos_version,
                    error=f"macOS 13.0+ required (found {macos_version})",
                )
        except (ValueError, IndexError):
            return ScreenCaptureInfo(
                available=False,
                version=macos_version,
                error="Could not parse macOS version",
            )

        # Check if binary exists
        if not self._binary_path:
            return ScreenCaptureInfo(
                available=False,
                version=macos_version,
                error="screencapture-recorder binary not found",
            )

        # Optional: Check permission directly via Quartz (if available)
        # This helps diagnose permission issues before testing the binary
        try:
            from Quartz import CGPreflightScreenCaptureAccess

            has_permission = CGPreflightScreenCaptureAccess()
            if not has_permission:
                self.logger.warning("Screen Recording permission not granted to app")
                return ScreenCaptureInfo(
                    available=False,
                    version=macos_version,
                    error="Screen Recording permission not granted. Please enable it in System Settings → Privacy & Security → Screen Recording",
                )
            else:
                self.logger.info("Screen Recording permission confirmed via Quartz")
        except ImportError:
            # Quartz not available - continue with binary test
            self.logger.debug(
                "Quartz not available for permission check, continuing with binary test"
            )
        except Exception as e:
            self.logger.debug(
                f"Permission check via Quartz failed: {e}, continuing with binary test"
            )

        # Test if ScreenCaptureKit actually works (permissions, etc.)
        try:
            self.logger.info(
                f"Testing ScreenCaptureKit with binary: {self._binary_path}"
            )

            # Use Popen instead of run() to properly handle timeout and kill
            # WHY: subprocess.run() with timeout leaves zombie processes if it times out
            process = subprocess.Popen(
                [str(self._binary_path), "test"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                stdout, stderr = process.communicate(timeout=10)
                returncode = process.returncode
            except subprocess.TimeoutExpired:
                # IMPORTANT: Kill the process on timeout to prevent zombie processes
                process.kill()
                process.wait()
                self.logger.error("ScreenCaptureKit test timed out - process killed")
                return ScreenCaptureInfo(
                    available=False,
                    version=macos_version,
                    error="Test command timed out (permissions may not be granted)",
                )

            # Log full output - use INFO level so it's visible
            stdout_preview = stdout[:1000] if stdout else ""
            stderr_preview = stderr[:1000] if stderr else ""
            self.logger.info(f"Binary test result: returncode={returncode}")
            if stdout_preview:
                self.logger.info(f"  stdout: {stdout_preview}")
            if stderr_preview:
                self.logger.info(f"  stderr: {stderr_preview}")

            if returncode == 0:
                self.logger.info("ScreenCaptureKit test passed - available for use")
                return ScreenCaptureInfo(
                    available=True, version=macos_version, error=None
                )
            else:
                # Combine stdout and stderr for error message
                # Swift prints errors to stdout, not stderr
                output = (stdout or "").strip()
                error_output = (stderr or "").strip()

                # Prefer stdout for error messages (Swift prints there)
                if error_output:
                    error_msg = (
                        f"{output}\n{error_output}".strip() if output else error_output
                    )
                else:
                    error_msg = output if output else "Unknown error (no output)"

                self.logger.warning(
                    f"ScreenCaptureKit test failed (exit {returncode}): {error_msg}"
                )
                return ScreenCaptureInfo(
                    available=False,
                    version=macos_version,
                    error=f"Test failed (exit {returncode}): {error_msg}",
                )
        except FileNotFoundError:
            error_msg = f"Binary not found or not executable: {self._binary_path}"
            self.logger.error(error_msg)
            return ScreenCaptureInfo(
                available=False, version=macos_version, error=error_msg
            )
        except PermissionError:
            error_msg = f"Permission denied executing binary: {self._binary_path}"
            self.logger.error(error_msg)
            return ScreenCaptureInfo(
                available=False, version=macos_version, error=error_msg
            )
        except Exception as e:
            error_msg = f"Test error: {str(e)}"
            self.logger.error(
                f"ScreenCaptureKit test exception: {error_msg}", exc_info=True
            )
            return ScreenCaptureInfo(
                available=False, version=macos_version, error=error_msg
            )

    def list_displays(self) -> list[dict]:
        """
        List available displays

        Returns:
            List of display info dictionaries
        """
        if not self._binary_path:
            return []

        try:
            result = subprocess.run(
                [str(self._binary_path), "list-devices"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                # Parse output to extract display information
                displays = []
                lines = result.stdout.split("\n")
                for line in lines:
                    if line.strip().startswith("[") and "x" in line:
                        # Parse: "  [0] 12345 - 1920x1080"
                        try:
                            parts = line.strip().split()
                            index = parts[0].strip("[]")
                            display_id = parts[1]
                            resolution = parts[3]
                            displays.append(
                                {
                                    "index": int(index),
                                    "id": display_id,
                                    "resolution": resolution,
                                }
                            )
                        except (IndexError, ValueError):
                            continue

                return displays

        except Exception as e:
            self.logger.error(f"Error listing displays: {e}")

        return []

    def start_recording(
        self,
        output_path: Path,
        duration: Optional[float] = None,
        display_id: Optional[str] = None,
    ) -> bool:
        """
        Start recording system audio

        Args:
            output_path: Path where to save the recording
            duration: Recording duration in seconds (None = until stop_recording is called)
            display_id: Display ID to record from (None = main display)

        Returns:
            True if recording started successfully
        """
        if self._recording_process is not None:
            self.logger.warning("Recording already in progress")
            return False

        if not self._binary_path:
            self.logger.error("screencapture-recorder binary not available")
            return False

        # Build command
        cmd = [str(self._binary_path), "record", "--output", str(output_path)]

        if duration is not None:
            cmd.extend(["--duration", str(duration)])
        else:
            # Default to a very long duration if not specified
            # We'll kill the process manually when stop_recording is called
            cmd.extend(["--duration", "3600"])  # 1 hour max

        if display_id is not None:
            cmd.extend(["--display", str(display_id)])

        try:
            # Start the recording process
            self._recording_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            self._current_output_path = output_path
            self._start_time = time.time()
            self._stop_event.clear()

            # Start monitor thread to check process status
            self._monitor_thread = threading.Thread(
                target=self._monitor_recording, daemon=True
            )
            self._monitor_thread.start()

            # Give it a moment to start and fail early if there's a problem
            time.sleep(0.5)

            if self._recording_process.poll() is not None:
                # Process already exited
                stdout, stderr = self._recording_process.communicate()

                # Check if it's a permission issue
                if (
                    "Start stream failed" in stderr
                    or "Operation not permitted" in stderr
                ):
                    self.logger.error(
                        "Screen Recording permission required. "
                        "Please grant permission in: "
                        "System Settings → Privacy & Security → Screen Recording"
                    )
                else:
                    self.logger.error(f"Recording failed to start: {stderr}")

                self._recording_process = None
                return False

            self.logger.info(f"ScreenCaptureKit recording started: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error starting recording: {e}")
            self._recording_process = None
            return False

    def _monitor_recording(self):
        """Monitor the recording process in a background thread"""
        while not self._stop_event.is_set() and self._recording_process:
            if self._recording_process.poll() is not None:
                # Process finished
                stdout, stderr = self._recording_process.communicate()
                if self._recording_process.returncode != 0:
                    self.logger.error(f"Recording process failed: {stderr}")
                break
            time.sleep(0.1)

    def stop_recording(self) -> Optional[Path]:
        """
        Stop the current recording

        Returns:
            Path to the recorded file, or None if no recording was active
        """
        if self._recording_process is None:
            self.logger.warning("No recording in progress")
            return None

        try:
            # Signal stop
            self._stop_event.set()

            # Send SIGINT (like Ctrl+C) for graceful shutdown
            # This should trigger the signal handler in the Swift binary
            import signal as sig

            self._recording_process.send_signal(sig.SIGINT)

            # Wait longer for graceful shutdown (10 seconds)
            try:
                self._recording_process.wait(timeout=10)
                self.logger.info("Recording process stopped gracefully")
            except subprocess.TimeoutExpired:
                # If SIGINT didn't work, try SIGTERM
                self.logger.warning("SIGINT timeout, trying SIGTERM...")
                self._recording_process.terminate()
                try:
                    self._recording_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    # Force kill if nothing else works
                    self.logger.warning("Recording process didn't stop, killing...")
                    self._recording_process.kill()
                    self._recording_process.wait()

            output_path = self._current_output_path

            # Clean up
            self._recording_process = None
            self._current_output_path = None

            # Wait for monitor thread
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=2)

            self.logger.info(f"Recording stopped: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Error stopping recording: {e}")
            return None

    def get_recording_duration(self) -> float:
        """
        Get current recording duration in seconds

        Returns:
            Duration in seconds, or 0.0 if not recording
        """
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def is_recording(self) -> bool:
        """
        Check if currently recording

        Returns:
            True if recording is in progress
        """
        return (
            self._recording_process is not None
            and self._recording_process.poll() is None
        )


