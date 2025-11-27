"""
ScreenCaptureKit Audio Recorder Python Wrapper

This module provides a Python interface to the Swift ScreenCaptureKit tool
for recording system audio on macOS 13.0+ without requiring BlackHole.
"""
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
        possible_paths = [
            # Development build location
            Path(__file__).parent.parent / "packaging/screencapture_tool/.build/release/screencapture-recorder",
            Path(__file__).parent.parent / "packaging/screencapture_tool/.build/arm64-apple-macosx/release/screencapture-recorder",

            # Packaged application location (when using PyInstaller)
            Path(sys._MEIPASS) / "screencapture-recorder" if getattr(sys, 'frozen', False) else None,

            # System-wide installation
            Path("/usr/local/bin/screencapture-recorder"),
        ]

        for path in possible_paths:
            if path and path.exists() and path.is_file():
                self._binary_path = path
                self.logger.info(f"Found screencapture-recorder at: {path}")
                return True

        self.logger.warning("screencapture-recorder binary not found")
        return False

    def is_available(self) -> ScreenCaptureInfo:
        """
        Check if ScreenCaptureKit is available on this system

        Returns:
            ScreenCaptureInfo with availability status
        """
        # Check macOS version first
        if platform.system() != 'Darwin':
            return ScreenCaptureInfo(
                available=False,
                version="N/A",
                error="ScreenCaptureKit only available on macOS"
            )

        # Parse macOS version
        macos_version = platform.mac_ver()[0]
        try:
            major, minor = map(int, macos_version.split('.')[:2])
            if major < 13:  # macOS 13.0 (Ventura) required
                return ScreenCaptureInfo(
                    available=False,
                    version=macos_version,
                    error=f"macOS 13.0+ required (found {macos_version})"
                )
        except (ValueError, IndexError):
            return ScreenCaptureInfo(
                available=False,
                version=macos_version,
                error="Could not parse macOS version"
            )

        # Check if binary exists
        if not self._binary_path:
            return ScreenCaptureInfo(
                available=False,
                version=macos_version,
                error="screencapture-recorder binary not found"
            )

        # Test if ScreenCaptureKit actually works (permissions, etc.)
        try:
            result = subprocess.run(
                [str(self._binary_path), "test"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                return ScreenCaptureInfo(
                    available=True,
                    version=macos_version,
                    error=None
                )
            else:
                return ScreenCaptureInfo(
                    available=False,
                    version=macos_version,
                    error=f"Test failed: {result.stderr}"
                )

        except subprocess.TimeoutExpired:
            return ScreenCaptureInfo(
                available=False,
                version=macos_version,
                error="Test command timed out"
            )
        except Exception as e:
            return ScreenCaptureInfo(
                available=False,
                version=macos_version,
                error=f"Test failed: {str(e)}"
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
                timeout=5
            )

            if result.returncode == 0:
                # Parse output to extract display information
                displays = []
                lines = result.stdout.split('\n')
                for line in lines:
                    if line.strip().startswith('[') and 'x' in line:
                        # Parse: "  [0] 12345 - 1920x1080"
                        try:
                            parts = line.strip().split()
                            index = parts[0].strip('[]')
                            display_id = parts[1]
                            resolution = parts[3]
                            displays.append({
                                'index': int(index),
                                'id': display_id,
                                'resolution': resolution
                            })
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
        display_id: Optional[str] = None
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
        cmd = [
            str(self._binary_path),
            "record",
            "--output", str(output_path)
        ]

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
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            self._current_output_path = output_path
            self._start_time = time.time()
            self._stop_event.clear()

            # Start monitor thread to check process status
            self._monitor_thread = threading.Thread(
                target=self._monitor_recording,
                daemon=True
            )
            self._monitor_thread.start()

            # Give it a moment to start and fail early if there's a problem
            time.sleep(0.5)

            if self._recording_process.poll() is not None:
                # Process already exited
                stdout, stderr = self._recording_process.communicate()

                # Check if it's a permission issue
                if "Start stream failed" in stderr or "Operation not permitted" in stderr:
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
        return self._recording_process is not None and self._recording_process.poll() is None


def test_screencapture():
    """Test function for the ScreenCaptureRecorder"""
    print("=== ScreenCaptureKit Recorder Test ===\n")

    recorder = ScreenCaptureRecorder()

    # Check availability
    info = recorder.is_available()
    print(f"Available: {info.available}")
    print(f"macOS Version: {info.version}")
    if info.error:
        print(f"Error: {info.error}")
        return

    print("\n✓ ScreenCaptureKit is available!")

    # List displays
    print("\nDisplays:")
    displays = recorder.list_displays()
    for display in displays:
        print(f"  [{display['index']}] {display['id']} - {display['resolution']}")

    # Test recording (5 seconds)
    print("\nTesting 5-second recording...")
    test_file = Path("/tmp/screencapture_test.wav")

    if recorder.start_recording(test_file, duration=5):
        print("Recording started...")

        # Monitor duration
        while recorder.is_recording():
            duration = recorder.get_recording_duration()
            print(f"Recording: {duration:.1f}s", end='\r')
            time.sleep(0.1)

        print(f"\n✓ Recording complete: {test_file}")

        # Check file
        if test_file.exists():
            data, sr = sf.read(test_file)
            print(f"  Sample rate: {sr} Hz")
            print(f"  Channels: {data.shape[1] if data.ndim > 1 else 1}")
            print(f"  Duration: {len(data) / sr:.1f}s")
            print(f"  Peak level: {np.max(np.abs(data)):.3f}")
    else:
        print("✗ Failed to start recording")


if __name__ == "__main__":
    test_screencapture()
