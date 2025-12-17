"""
System Audio Recorder mit BlackHole Support (macOS)
"""

from pathlib import Path
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum
import time
import numpy as np
import soundfile as sf
import threading

from config import RECORDING_SAMPLE_RATE, RECORDING_CHANNELS, RECORDING_FORMAT, TEMP_DIR
from utils.logger import get_logger
from utils.error_handler import error_handler
from utils.audio_processing import trim_leading_silence

logger = get_logger()


class RecordingBackend(Enum):
    """Recording Backend Options"""

    SCREENCAPTURE_KIT = "screencapture_kit"  # macOS 13+ native ScreenCaptureKit
    BLACKHOLE = "blackhole"  # BlackHole virtual audio driver
    AUTO = "auto"  # Auto-select best available


class RecordingState(Enum):
    """Recording States"""

    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class RecordingInfo:
    """Informationen über eine Aufnahme"""

    duration_seconds: float
    sample_rate: int
    channels: int
    file_path: Optional[Path] = None
    peak_level: float = 0.0  # Peak audio level (0.0 - 1.0)
    trimmed_silence_duration: float = (
        0.0  # Duration of silence trimmed from start (seconds)
    )


class Recorder:
    """System Audio Recorder"""

    def __init__(self, backend: RecordingBackend = RecordingBackend.AUTO):
        self.logger = logger
        self.state = RecordingState.IDLE

        # Recording Parameters
        self.sample_rate = RECORDING_SAMPLE_RATE
        self.channels = RECORDING_CHANNELS
        self.dtype = RECORDING_FORMAT

        # Recording Data
        self.recorded_chunks: List[np.ndarray] = []
        self.recording_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Monitoring (level metering without recording)
        self.monitoring_thread: Optional[threading.Thread] = None
        self._monitoring_stop_event = threading.Event()
        self._is_monitoring = False

        # Callbacks
        self.level_callback: Optional[Callable[[float], None]] = None

        # Level Meter Ballistics (professional audio meter behavior)
        # Attack time: how quickly meter responds to increasing signal (300ms = VU meter standard)
        # Release time: how quickly meter falls when signal decreases (600ms for smooth, pleasant decay)
        self.attack_time_ms = 300.0  # Fast response to peaks
        self.release_time_ms = 600.0  # Slower, smoother decay
        self.current_level = 0.0  # Current smoothed level (0.0-1.0)

        # Display range for dBFS scale
        # Professional meters typically show -60 dBFS to 0 dBFS
        # -60 dBFS is very quiet (digital silence threshold)
        # 0 dBFS is digital full scale (clipping point)
        self.db_range_min = -60.0  # Bottom of meter
        self.db_range_max = 0.0  # Top of meter (clipping)

        # Backend selection
        self.backend = backend
        self._selected_backend: Optional[RecordingBackend] = None

        # SoundCard (for BlackHole backend)
        self._soundcard = None
        self._import_soundcard()

        # ScreenCaptureKit (for ScreenCaptureKit backend)
        self._screencapture = None
        self._screencapture_output_path: Optional[Path] = None
        self._import_screencapture()

        # Detect and select backend
        if self.backend == RecordingBackend.AUTO:
            self._select_best_backend()
        else:
            self._selected_backend = self.backend

        self.logger.info(f"Recorder initialized with backend: {self._selected_backend}")

    def _import_soundcard(self) -> bool:
        """Importiert SoundCard Library"""
        try:
            import soundcard as sc

            self._soundcard = sc
            self.logger.info("SoundCard library loaded")
            return True
        except ImportError:
            self.logger.warning(
                "SoundCard not installed. BlackHole backend will not be available."
            )
            return False

    def _import_screencapture(self) -> bool:
        """Import ScreenCaptureKit wrapper"""
        try:
            from core.screencapture_recorder import ScreenCaptureRecorder

            self._screencapture = ScreenCaptureRecorder()
            info = self._screencapture.is_available()
            if info.available:
                self.logger.info(f"ScreenCaptureKit available (macOS {info.version})")
                return True
            else:
                self.logger.info(f"ScreenCaptureKit not available: {info.error}")
                return False
        except Exception as e:
            self.logger.warning(f"ScreenCaptureKit not available: {e}")
            return False

    def _select_best_backend(self):
        """Auto-select the best available recording backend"""
        # Prefer ScreenCaptureKit on macOS 13+ (no driver installation needed)
        if self._screencapture and self._screencapture.is_available().available:
            self._selected_backend = RecordingBackend.SCREENCAPTURE_KIT
            self.logger.info(
                "Auto-selected ScreenCaptureKit backend (native macOS 13+)"
            )
        elif self._soundcard and self.find_blackhole_device():
            self._selected_backend = RecordingBackend.BLACKHOLE
            self.logger.info("Auto-selected BlackHole backend")
        elif self._soundcard:
            # SoundCard available but no BlackHole - still use it for other devices
            self._selected_backend = RecordingBackend.BLACKHOLE
            self.logger.warning(
                "BlackHole not found, but SoundCard available for other devices"
            )
        else:
            self._selected_backend = None
            self.logger.error("No recording backend available")

    def get_available_devices(self) -> List[str]:
        """
        Gibt Liste verfügbarer Audio-Devices zurück

        Returns:
            Liste von Input-Device-Namen (nur diese können für Recording verwendet werden)
        """
        if not self._soundcard:
            return []

        try:
            microphones = self._soundcard.all_microphones()

            devices = []

            # Add only input devices - these are the only ones we can record from
            for mic in microphones:
                devices.append(mic.name)

            return devices

        except Exception as e:
            self.logger.error(f"Error getting audio devices: {e}")
            return []

    def find_blackhole_device(self) -> Optional[any]:
        """
        Sucht nach BlackHole Audio-Device

        Returns:
            BlackHole Device oder None
        """
        if not self._soundcard:
            return None

        try:
            # Suche in Microphones (Loopback)
            microphones = self._soundcard.all_microphones()

            for mic in microphones:
                if "blackhole" in mic.name.lower():
                    self.logger.info(f"Found BlackHole device: {mic.name}")
                    return mic

            self.logger.warning("BlackHole device not found")
            return None

        except Exception as e:
            self.logger.error(f"Error finding BlackHole device: {e}")
            return None

    def start_recording(
        self,
        device_name: Optional[str] = None,
        level_callback: Optional[Callable[[float], None]] = None,
    ) -> bool:
        """
        Startet Aufnahme

        Args:
            device_name: Name des Recording-Devices (None = use selected backend)
            level_callback: Callback für Audio-Level Updates

        Returns:
            True wenn erfolgreich gestartet
        """
        if self.state == RecordingState.RECORDING:
            self.logger.warning("Already recording")
            return False

        # Stop monitoring if active
        if self._is_monitoring:
            self.logger.info("Stopping monitoring before starting recording")
            self.stop_monitoring()

        # If device_name is None, use the selected backend
        if (
            device_name is None
            and self._selected_backend == RecordingBackend.SCREENCAPTURE_KIT
        ):
            # Use ScreenCaptureKit
            if not self._screencapture:
                self.logger.error("ScreenCaptureKit not available")
                return False

            return self._start_screencapture_recording(level_callback)

        # Otherwise use SoundCard/BlackHole (existing logic)
        if not self._soundcard:
            self.logger.error("SoundCard not available")
            return False

        # Finde Device
        if device_name:
            self.logger.info(f"Looking for device: '{device_name}'")

            # Suche spezifisches Device
            device = None
            for mic in self._soundcard.all_microphones():
                if (
                    device_name == mic.name
                    or device_name in mic.name
                    or mic.name in device_name
                ):
                    device = mic
                    self.logger.info(f"Found matching device: {mic.name}")
                    break
        else:
            # Default: BlackHole
            device = self.find_blackhole_device()

        if not device:
            self.logger.error(f"No recording device found for: {device_name}")
            # Debug: Liste alle verfügbaren Microphones
            try:
                all_mics = self._soundcard.all_microphones()
                self.logger.error(
                    f"Available microphones: {[mic.name for mic in all_mics]}"
                )
            except:
                pass
            return False

        self.logger.info(f"Starting recording from: {device.name}")

        # Reset State
        self.recorded_chunks = []
        self._stop_event.clear()
        self.level_callback = level_callback
        self.current_level = 0.0  # Reset ballistics filter
        self.state = RecordingState.RECORDING

        # Starte Recording Thread
        self.recording_thread = threading.Thread(
            target=self._record_loop, args=(device,), daemon=True
        )
        self.recording_thread.start()

        return True

    def _start_screencapture_recording(
        self, level_callback: Optional[Callable[[float], None]]
    ) -> bool:
        """
        Start recording using ScreenCaptureKit

        Args:
            level_callback: Callback for audio level updates

        Returns:
            True if started successfully
        """
        from pathlib import Path
        import tempfile

        # Create temporary output file
        temp_dir = Path(tempfile.gettempdir())
        output_path = temp_dir / f"screencapture_recording_{int(time.time())}.wav"

        # Start ScreenCaptureKit recording
        success = self._screencapture.start_recording(output_path=output_path)

        if not success:
            self.logger.error("Failed to start ScreenCaptureKit recording")
            return False

        # Store recording info
        self._screencapture_output_path = output_path
        self.level_callback = level_callback
        self.current_level = 0.0
        self.state = RecordingState.RECORDING

        self.logger.info(f"ScreenCaptureKit recording started: {output_path}")

        # Start level monitoring thread
        self.recording_thread = threading.Thread(
            target=self._screencapture_monitor_loop, daemon=True
        )
        self.recording_thread.start()

        return True

    def get_current_level(self) -> float:
        """
        Get current audio level (0.0-1.0)

        Returns:
            Current smoothed level
        """
        return self.current_level

    def _screencapture_monitor_loop(self):
        """Monitor ScreenCaptureKit recording and provide level updates"""
        import time

        self.logger.info("Starting ScreenCaptureKit monitor loop")
        last_log_time = 0
        last_update_time = time.time()

        while self.state == RecordingState.RECORDING:
            # Level update from growing file
            if (
                self._screencapture_output_path
                and self._screencapture_output_path.exists()
            ):
                try:
                    # Read raw bytes from the growing file (skip WAV header parsing which fails on incomplete files)
                    # Format: Float32 (4 bytes), Stereo (2 channels) -> 8 bytes per frame
                    # Sample rate: 48000 Hz
                    bytes_per_frame = 8
                    frames_needed = int(48000 * 0.1)  # Last 100ms
                    bytes_needed = frames_needed * bytes_per_frame

                    file_size = self._screencapture_output_path.stat().st_size

                    current_time = time.time()

                    # Log file size periodically (debug)
                    if current_time - last_log_time > 2.0:
                        self.logger.debug(
                            f"Monitor: File size {file_size} bytes, Path: {self._screencapture_output_path}"
                        )
                        last_log_time = current_time

                    # WAV header is typically 44 bytes
                    if file_size > 44:
                        with open(self._screencapture_output_path, "rb") as f:
                            # Determine where to seek
                            if file_size - 44 < bytes_needed:
                                # File is smaller than window, read what we have
                                f.seek(44)
                            else:
                                # Seek to end minus window
                                f.seek(max(44, file_size - bytes_needed))

                            raw_data = f.read()

                            if raw_data:
                                # Convert to numpy array
                                try:
                                    audio_data = np.frombuffer(
                                        raw_data, dtype=np.float32
                                    )

                                    if len(audio_data) > 0:
                                        # Calculate RMS
                                        rms = np.sqrt(np.mean(audio_data**2))
                                        dbfs = self._rms_to_dbfs(rms)
                                        level = self._dbfs_to_display(dbfs)

                                        # Calculate time delta for ballistics
                                        dt = current_time - last_update_time
                                        last_update_time = current_time

                                        # Update level with ballistics
                                        self.current_level = float(
                                            self._apply_ballistics(level, dt)
                                        )

                                        # Call callback
                                        if self.level_callback:
                                            try:
                                                self.level_callback(self.current_level)
                                            except Exception as e:
                                                self.logger.error(
                                                    f"Error in level callback: {e}"
                                                )
                                except Exception as e:
                                    self.logger.error(f"Monitor conversion error: {e}")
                except Exception as e:
                    self.logger.error(f"Monitor error: {e}")
            else:
                if time.time() - last_log_time > 2.0:
                    self.logger.warning(
                        f"Monitor: Output file not found or path not set: {self._screencapture_output_path}"
                    )
                    last_log_time = time.time()

            time.sleep(0.1)  # Update every 100ms

    def _stop_screencapture_recording(
        self, save_path: Optional[Path] = None
    ) -> Optional[RecordingInfo]:
        """
        Stop ScreenCaptureKit recording and save file

        Args:
            save_path: Path to save (default: temp)

        Returns:
            RecordingInfo or None on error
        """
        import shutil

        # Stop ScreenCaptureKit recording
        self.state = RecordingState.STOPPED
        output_path = self._screencapture.stop_recording()

        if not output_path or not output_path.exists():
            self.logger.error("ScreenCaptureKit recording failed - no output file")
            return None

        try:
            # Read the file to get info
            data, sr = sf.read(str(output_path))

            # Check if file has any data
            if len(data) == 0:
                self.logger.error(
                    "ScreenCaptureKit recording is empty - no audio samples captured"
                )
                self.logger.error("Possible causes:")
                self.logger.error("  - Screen Recording permission not granted")
                self.logger.error("  - No audio was playing during recording")
                self.logger.error("  - macOS audio routing issue")
                return None

            # Trim leading silence (automatic for recordings)
            data, trimmed_duration = trim_leading_silence(
                data, sr, threshold_db=-40.0, min_silence_duration=0.5
            )

            duration = len(data) / sr
            peak_level = float(np.max(np.abs(data)))

            self.logger.info(f"Recorded {duration:.1f}s, peak level: {peak_level:.2f}")

            # Determine final save path
            if save_path:
                final_path = Path(save_path)
                final_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                # Default: Temp directory
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                final_path = TEMP_DIR / f"recording_{timestamp}.wav"
                final_path.parent.mkdir(parents=True, exist_ok=True)

            # Write trimmed audio to final location
            sf.write(str(final_path), data, sr)

            # Clean up temporary file
            if output_path.exists() and output_path != final_path:
                output_path.unlink()

            self.logger.info(f"Recording saved: {final_path}")

            # Reset state
            self.state = RecordingState.IDLE
            self._screencapture_output_path = None

            return RecordingInfo(
                duration_seconds=duration,
                sample_rate=int(sr),
                channels=data.shape[1] if data.ndim > 1 else 1,
                file_path=final_path,
                peak_level=peak_level,
                trimmed_silence_duration=trimmed_duration,
            )

        except Exception as e:
            self.logger.error(
                f"Error saving ScreenCaptureKit recording: {e}", exc_info=True
            )
            return None

    def _rms_to_dbfs(self, rms: float) -> float:
        """
        Convert RMS value to dBFS (decibels relative to full scale)

        WHY: Professional audio meters use dBFS scale where:
             - 0 dBFS = maximum possible digital level (clipping)
             - -∞ dBFS = digital silence
             - Full-scale sine wave RMS = 0 dBFS (standard definition per AES17)

        Formula: dBFS = 20 * log10(rms * sqrt(2))
        The sqrt(2) factor ensures a full-scale sine wave (RMS = 1/sqrt(2)) reads as 0 dBFS
        """
        if rms <= 1e-10:  # Avoid log(0) which would be -infinity
            return -100.0  # Very quiet, below useful display range

        # Standard dBFS calculation (AES17-1998 standard)
        db = 20.0 * np.log10(rms * np.sqrt(2.0))
        return float(db)

    def _dbfs_to_display(self, dbfs: float) -> float:
        """
        Convert dBFS to display level (0.0-1.0) based on meter range

        WHY: GUI meters show a limited range (typically -60 to 0 dBFS)
             Map this range to 0.0-1.0 for progress bar display

        Example: If meter range is -60 to 0 dBFS:
                 -60 dBFS → 0.0 (empty)
                 -30 dBFS → 0.5 (halfway)
                   0 dBFS → 1.0 (full/clipping)
        """
        # Clamp to display range
        dbfs = max(self.db_range_min, min(self.db_range_max, dbfs))

        # Map to 0.0-1.0
        range_width = self.db_range_max - self.db_range_min
        level = (dbfs - self.db_range_min) / range_width
        return float(level)

    def _apply_ballistics(self, target_level: float, dt_seconds: float) -> float:
        """
        Apply ballistics filter (attack/release smoothing) to level meter

        WHY: Professional audio meters don't jump instantly - they have:
             - Attack time: Fast response when signal increases (prevents missing peaks)
             - Release time: Slow decay when signal decreases (smooth, readable display)

             This mimics analog VU meters and prevents flickering

        Args:
            target_level: New measured level (0.0-1.0)
            dt_seconds: Time since last update in seconds

        Returns:
            Smoothed level (0.0-1.0)
        """
        if target_level > self.current_level:
            # Signal increasing - use attack time (fast response)
            time_constant_ms = self.attack_time_ms
        else:
            # Signal decreasing - use release time (slow, smooth decay)
            time_constant_ms = self.release_time_ms

        # Calculate smoothing coefficient
        # Formula: alpha = 1 - exp(-dt / time_constant)
        # This creates an exponential moving average with the desired time constant
        time_constant_s = time_constant_ms / 1000.0
        alpha = 1.0 - np.exp(-dt_seconds / time_constant_s)

        # Apply exponential smoothing
        self.current_level = self.current_level + alpha * (
            target_level - self.current_level
        )

        return self.current_level

    def _record_loop(self, device):
        """Recording Loop (läuft in separatem Thread)"""
        try:
            # Blocksize: CoreAudio limits blocksize to 15-512
            # Use maximum allowed blocksize for best performance
            blocksize = 512

            # Update level meter every ~50ms (20 Hz) for smooth visual feedback
            # Too fast = flickering, too slow = laggy response
            update_interval = 0.05  # 50ms
            blocks_per_update = max(
                1, int((update_interval * self.sample_rate) / blocksize)
            )

            self.logger.debug(
                f"Recording with blocksize={blocksize}, "
                f"blocks_per_update={blocks_per_update} "
                f"(update every {update_interval*1000:.0f}ms)"
            )

            with device.recorder(
                samplerate=self.sample_rate, channels=self.channels, blocksize=blocksize
            ) as recorder:

                block_counter = 0
                accumulated_blocks = []
                last_update_time = time.time()

                while not self._stop_event.is_set():
                    if self.state != RecordingState.RECORDING:
                        # Pausiert - warte kurz
                        time.sleep(0.1)
                        continue

                    # Nehme Audio-Block auf
                    audio_block = recorder.record(numframes=blocksize)

                    # Speichere Chunk
                    self.recorded_chunks.append(audio_block)

                    # Akkumuliere Blöcke für RMS-Berechnung über längeres Fenster
                    accumulated_blocks.append(audio_block)
                    block_counter += 1

                    # Level-Update mit professioneller RMS-Berechnung und Ballistics
                    if self.level_callback and block_counter >= blocks_per_update:
                        current_time = time.time()
                        dt = current_time - last_update_time

                        # Berechne RMS über alle akkumulierten Blöcke
                        # WHY: Längeres Fenster = stabilere RMS-Messung
                        combined_audio = np.concatenate(accumulated_blocks, axis=0)
                        rms = np.sqrt(np.mean(combined_audio**2))

                        # Convert to dBFS (professional audio scale)
                        dbfs = self._rms_to_dbfs(rms)

                        # Convert to display level (0.0-1.0)
                        target_level = self._dbfs_to_display(dbfs)

                        # Apply ballistics filter (smooth attack/release)
                        smoothed_level = self._apply_ballistics(target_level, dt)

                        # Send to GUI
                        self.level_callback(smoothed_level)

                        # Reset for next update
                        block_counter = 0
                        accumulated_blocks = []
                        last_update_time = current_time

        except Exception as e:
            self.logger.error(f"Error in recording loop: {e}", exc_info=True)
            self.state = RecordingState.STOPPED

    def pause_recording(self) -> bool:
        """
        Pausiert Aufnahme

        Returns:
            True wenn erfolgreich
        """
        if self.state != RecordingState.RECORDING:
            return False

        self.state = RecordingState.PAUSED
        self.logger.info("Recording paused")
        return True

    def resume_recording(self) -> bool:
        """
        Setzt pausierte Aufnahme fort

        Returns:
            True wenn erfolgreich
        """
        if self.state != RecordingState.PAUSED:
            return False

        self.state = RecordingState.RECORDING
        self.logger.info("Recording resumed")
        return True

    def stop_recording(
        self, save_path: Optional[Path] = None
    ) -> Optional[RecordingInfo]:
        """
        Stoppt Aufnahme und speichert

        Args:
            save_path: Pfad zum Speichern (default: temp)

        Returns:
            RecordingInfo oder None bei Fehler
        """
        if self.state not in [RecordingState.RECORDING, RecordingState.PAUSED]:
            self.logger.warning("Not recording")
            return None

        self.logger.info("Stopping recording...")

        # Check if using ScreenCaptureKit
        if (
            self._selected_backend == RecordingBackend.SCREENCAPTURE_KIT
            and self._screencapture_output_path
        ):
            return self._stop_screencapture_recording(save_path)

        # Otherwise use SoundCard/BlackHole logic
        # Signalisiere Thread zu stoppen
        self._stop_event.set()
        self.state = RecordingState.STOPPED

        # Warte auf Thread
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)

        # Füge Chunks zusammen
        if not self.recorded_chunks:
            self.logger.warning("No audio recorded")
            return None

        try:
            # Concatenate alle Chunks
            audio_data = np.concatenate(self.recorded_chunks, axis=0)

            # Trim leading silence (automatic for recordings)
            audio_data, trimmed_duration = trim_leading_silence(
                audio_data,
                self.sample_rate,
                threshold_db=-40.0,
                min_silence_duration=0.5,
            )

            duration = len(audio_data) / self.sample_rate
            peak_level = float(np.max(np.abs(audio_data)))

            self.logger.info(
                f"Recorded {duration:.1f}s, " f"peak level: {peak_level:.2f}"
            )

            # Speichere wenn Pfad angegeben
            if save_path:
                save_path = Path(save_path)
                save_path.parent.mkdir(parents=True, exist_ok=True)

                sf.write(str(save_path), audio_data, self.sample_rate)

                self.logger.info(f"Recording saved to: {save_path}")

            else:
                # Default: Temp-Verzeichnis
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                save_path = TEMP_DIR / f"recording_{timestamp}.wav"
                save_path.parent.mkdir(parents=True, exist_ok=True)

                sf.write(str(save_path), audio_data, self.sample_rate)

                self.logger.info(f"Recording saved to temp: {save_path}")

            # Reset
            self.state = RecordingState.IDLE
            self.recorded_chunks = []

            return RecordingInfo(
                duration_seconds=duration,
                sample_rate=self.sample_rate,
                channels=self.channels,
                file_path=save_path,
                peak_level=peak_level,
                trimmed_silence_duration=trimmed_duration,
            )

        except Exception as e:
            self.logger.error(f"Error saving recording: {e}", exc_info=True)
            return None

    def get_recording_duration(self) -> float:
        """
        Gibt aktuelle Aufnahme-Dauer zurück

        Returns:
            Duration in Sekunden
        """
        # Check if actively using ScreenCaptureKit (indicated by output path being set)
        if self._screencapture_output_path and self._screencapture:
            return self._screencapture.get_recording_duration()

        # Fallback to standard chunk-based duration (BlackHole/SoundCard)
        if not self.recorded_chunks:
            return 0.0

        total_samples = sum(len(chunk) for chunk in self.recorded_chunks)
        return total_samples / self.sample_rate

    def get_state(self) -> RecordingState:
        """Gibt aktuellen Recording-State zurück"""
        return self.state

    def is_recording(self) -> bool:
        """Prüft ob gerade aufgenommen wird"""
        return self.state == RecordingState.RECORDING

    def cancel_recording(self):
        """Bricht Aufnahme ab ohne zu speichern"""
        if self.state in [RecordingState.RECORDING, RecordingState.PAUSED]:
            self.logger.info("Cancelling recording...")

            # ScreenCaptureKit Cleanup
            # WHY: ScreenCaptureKit subprocess must be stopped explicitly,
            # otherwise it keeps running and blocks subsequent recordings
            if (
                self._selected_backend == RecordingBackend.SCREENCAPTURE_KIT
                and self._screencapture
            ):
                self.logger.info(
                    "Stopping ScreenCaptureKit process due to cancellation"
                )
                self._screencapture.stop_recording()

                # Clean up temp file
                if (
                    self._screencapture_output_path
                    and self._screencapture_output_path.exists()
                ):
                    try:
                        self._screencapture_output_path.unlink()
                        self.logger.info(
                            f"Deleted temp file: {self._screencapture_output_path}"
                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to delete temp file: {e}")

                self._screencapture_output_path = None

            # Stoppe Thread
            self._stop_event.set()
            self.state = RecordingState.IDLE

            # Warte auf Thread
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=2.0)

            # Lösche Chunks
            self.recorded_chunks = []
            self.logger.info("Recording cancelled")

    def start_monitoring(
        self,
        device_name: Optional[str] = None,
        level_callback: Optional[Callable[[float], None]] = None,
    ) -> bool:
        """
        Start live audio monitoring (level metering without recording)

        WHY: Allows users to check input levels before starting actual recording

        Args:
            device_name: Name of the device to monitor (default: BlackHole)
            level_callback: Callback for audio level updates

        Returns:
            True if monitoring started successfully
        """
        if self._is_monitoring:
            self.logger.warning("Already monitoring")
            return False

        if self.state == RecordingState.RECORDING:
            self.logger.warning("Cannot monitor while recording")
            return False

        if not self._soundcard:
            self.logger.error("SoundCard not available")
            return False

        # Find device
        if device_name:
            self.logger.info(f"Looking for monitoring device: '{device_name}'")

            device = None
            for mic in self._soundcard.all_microphones():
                if (
                    device_name == mic.name
                    or device_name in mic.name
                    or mic.name in device_name
                ):
                    device = mic
                    self.logger.info(f"Found matching device: {mic.name}")
                    break
        else:
            # Default: BlackHole
            device = self.find_blackhole_device()

        if not device:
            self.logger.error(f"No monitoring device found for: {device_name}")
            return False

        self.logger.info(f"Starting monitoring from: {device.name}")

        # Setup monitoring
        self._monitoring_stop_event.clear()
        self.level_callback = level_callback
        self.current_level = 0.0  # Reset ballistics filter
        self._is_monitoring = True

        # Start monitoring thread
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop, args=(device,), daemon=True
        )
        self.monitoring_thread.start()

        return True

    def stop_monitoring(self):
        """Stop live audio monitoring"""
        if not self._is_monitoring:
            return

        self.logger.info("Stopping monitoring...")

        # Signal thread to stop
        self._monitoring_stop_event.set()
        self._is_monitoring = False

        # Wait for thread
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=2.0)

        # Reset level meter
        if self.level_callback:
            self.level_callback(0.0)

        self.logger.info("Monitoring stopped")

    def is_monitoring(self) -> bool:
        """Check if currently monitoring"""
        return self._is_monitoring

    def _monitoring_loop(self, device):
        """
        Monitoring loop (runs in separate thread)

        WHY: Similar to _record_loop but only monitors levels without recording
        """
        try:
            blocksize = 512
            update_interval = 0.05  # 50ms
            blocks_per_update = max(
                1, int((update_interval * self.sample_rate) / blocksize)
            )

            self.logger.debug(
                f"Monitoring with blocksize={blocksize}, "
                f"blocks_per_update={blocks_per_update}"
            )

            with device.recorder(
                samplerate=self.sample_rate, channels=self.channels, blocksize=blocksize
            ) as recorder:

                block_counter = 0
                accumulated_blocks = []
                last_update_time = time.time()

                while not self._monitoring_stop_event.is_set():
                    # Read audio block (but don't save it)
                    audio_block = recorder.record(numframes=blocksize)

                    # Accumulate blocks for RMS calculation
                    accumulated_blocks.append(audio_block)
                    block_counter += 1

                    # Level update with professional RMS calculation and ballistics
                    if self.level_callback and block_counter >= blocks_per_update:
                        current_time = time.time()
                        dt = current_time - last_update_time

                        # Calculate RMS over accumulated blocks
                        combined_audio = np.concatenate(accumulated_blocks, axis=0)
                        rms = np.sqrt(np.mean(combined_audio**2))

                        # Convert to dBFS
                        dbfs = self._rms_to_dbfs(rms)

                        # Convert to display level (0.0-1.0)
                        target_level = self._dbfs_to_display(dbfs)

                        # Apply ballistics filter
                        smoothed_level = self._apply_ballistics(target_level, dt)

                        # Send to GUI
                        self.level_callback(smoothed_level)

                        # Reset for next update
                        block_counter = 0
                        accumulated_blocks = []
                        last_update_time = current_time

        except Exception as e:
            self.logger.error(f"Error in monitoring loop: {e}", exc_info=True)
            self._is_monitoring = False

    def get_backend_info(self) -> dict:
        """
        Get information about the current recording backend

        Returns:
            Dictionary with backend info
        """
        return {
            "backend": self._selected_backend.value if self._selected_backend else None,
            "screencapture_available": self._screencapture is not None
            and self._screencapture.is_available().available,
            "blackhole_available": self._soundcard is not None
            and self.find_blackhole_device() is not None,
        }


# Globale Instanz
_recorder: Optional[Recorder] = None


def get_recorder() -> Recorder:
    """Gibt die globale Recorder-Instanz zurück"""
    global _recorder
    if _recorder is None:
        _recorder = Recorder()
    return _recorder
