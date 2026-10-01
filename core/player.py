"""
Audio Player - Real-time playback and mixing of separated stems

PURPOSE: Provides audio playback with per-stem volume/mute/solo controls
CONTEXT: Uses sounddevice for simple, reliable audio playback of pre-loaded audio
MIGRATION: Migrated from rtmixer to sounddevice.play() for simpler implementation
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Callable, List, Union
from dataclasses import dataclass
from enum import Enum
import threading
import time
import numpy as np
import soundfile as sf
from concurrent.futures import ThreadPoolExecutor

from config import RECORDING_SAMPLE_RATE
from utils.logger import get_logger
from utils.audio_processing import export_audio_chunks

logger = get_logger()


class PlaybackState(Enum):
    """Playback states"""

    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass
class StemSettings:
    """Settings for individual stem"""

    volume: float = 0.75  # 0.0 to 1.0
    is_muted: bool = False
    is_solo: bool = False


@dataclass
class PlaybackInfo:
    """Current playback information"""

    position_seconds: float
    duration_seconds: float
    state: PlaybackState


@dataclass
class AudioDeviceInfo:
    """An output device as exposed by PortAudio."""

    index: int
    name: str
    host_api: str
    max_channels: int
    default_sample_rate: float
    is_default: bool = False

    @property
    def label(self) -> str:
        return f"{self.name} ({self.host_api}, {self.max_channels}ch)"

    def __repr__(self) -> str:
        return self.label

class AudioPlayer:
    """
    Audio player with stem mixing capabilities using sounddevice

    Features:
    - Load multiple stems (audio files)
    - Simple playback with sounddevice.play()
    - Per-stem volume, mute, solo
    - Master volume control
    - Position seeking
    - Callbacks for position updates

    IMPLEMENTATION:
    - Uses sounddevice.play() for straightforward playback of pre-loaded audio
    - All stems are mixed in memory before playback
    - Non-blocking playback with position tracking thread
    """

    def __init__(self, sample_rate: int = RECORDING_SAMPLE_RATE):
        self.logger = logger
        self.sample_rate = sample_rate

        # Playback state
        self.state = PlaybackState.STOPPED
        self.position_samples = 0
        self.duration_samples = 0

        # Audio data
        self.stems: Dict[str, np.ndarray] = (
            {}
        )  # stem_name -> audio_data (channels, samples)
        self.stem_settings: Dict[str, StemSettings] = {}
        self.master_volume: float = 1.0

        # Loop mode state
        self.loop_mode_enabled: bool = False
        self.loop_start_samples: int = 0
        self.loop_end_samples: int = 0
        self._loop_cached_audio: Optional[np.ndarray] = (
            None  # Cached loop audio buffer (multi-rep)
        )
        self._loop_single_length: int = 0  # Length of single loop iteration in samples

        # Threading for position updates
        self._position_lock = threading.Lock()
        self._update_thread: Optional[threading.Thread] = None
        self._stop_update = threading.Event()

        # Thread pool for async operations (reduces thread creation overhead)
        self._thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="player")

        # Callbacks
        self.position_callback: Optional[Callable[[float, float], None]] = (
            None  # (position, duration)
        )
        self.state_callback: Optional[Callable[[PlaybackState], None]] = None

        # Sounddevice for playback
        self._output_device: Optional[int] = None
        self.last_error: Optional[str] = None
        self._sounddevice_module = None
        self._active_actions = []  # Track active playback for cancellation
        self._import_sounddevice()

        self.logger.info("AudioPlayer initialized with sounddevice")

    def _import_sounddevice(self) -> bool:
        """Import the sounddevice library for playback"""
        try:
            import sounddevice as sd

            self._sounddevice_module = sd
            self.logger.info("sounddevice library loaded for playback")

            # Log default audio device information
            try:
                default_device = sd.default.device
                self.logger.info(
                    f"sounddevice default devices: input={default_device[0]}, output={default_device[1]}"
                )
                device_info = sd.query_devices(
                    default_device[1]
                )  # [1] is output device
                self.logger.info(
                    f"Default audio output device: '{device_info['name']}'"
                )
                self.logger.info(
                    f"  - Max output channels: {device_info['max_output_channels']}"
                )
                self.logger.info(
                    f"  - Default sample rate: {device_info['default_samplerate']} Hz"
                )
                self.logger.info(
                    f"  - Host API: {sd.query_hostapis(device_info['hostapi'])['name']}"
                )
            except Exception as e:
                self.logger.warning(
                    f"Could not query audio device info: {e}", exc_info=True
                )

            return True
        except ImportError as e:
            self.logger.warning(f"sounddevice not installed: {e}")
            self.logger.warning("Install with: pip install sounddevice")
            self._sounddevice_module = None
            return False
        except OSError as e:
            # PortAudio not available (common in headless environments)
            self.logger.warning(f"sounddevice initialization failed: {e}")
            self.logger.warning(
                "This is normal in headless environments or without audio devices"
            )
            self._sounddevice_module = None
            return False

    # ------------------------------------------------------------------
    # Output device management
    # ------------------------------------------------------------------

    def list_output_devices(self) -> List[AudioDeviceInfo]:
        """
        Enumerate playable output devices.

        WHY: Windows exposes the same endpoint through several host APIs and
        Linux exposes hardware through ALSA *and* PulseAudio, so the UI must
        show the host API next to the name — otherwise users select the wrong
        'Speakers' entry and hear nothing.
        """
        sd = self._sounddevice_module
        if sd is None:
            return []

        try:
            devices = sd.query_devices()
            default_index = sd.default.device[1]
        except Exception as exc:
            self.last_error = f"Could not query audio devices: {exc}"
            self.logger.error(self.last_error)
            return []

        result: List[AudioDeviceInfo] = []
        for index, info in enumerate(devices):
            if info.get("max_output_channels", 0) <= 0:
                continue
            try:
                host_api = sd.query_hostapis(info["hostapi"])["name"]
            except Exception:  # pragma: no cover - malformed hostapi entry
                host_api = "Unknown"
            result.append(
                AudioDeviceInfo(
                    index=index,
                    name=info["name"],
                    host_api=host_api,
                    max_channels=int(info["max_output_channels"]),
                    default_sample_rate=float(info.get("default_samplerate") or 0.0),
                    is_default=(index == default_index),
                )
            )
        return result

    def set_output_device(self, device: Optional[Union[int, str]]) -> tuple:
        """
        Choose the output device for stem playback.

        Args:
            device: index, name substring (case-insensitive), or None for the
                    system default output.

        Returns:
            (success, message); the UI displays the message verbatim so a bad
            choice never looks like a silent failure.
        """
        if self._sounddevice_module is None:
            self._output_device = None
            self.last_error = "sounddevice/PortAudio unavailable; playback disabled."
            return False, self.last_error

        available = self.list_output_devices()

        if device is None:
            self._output_device = None
            self.last_error = None
            default = next((d for d in available if d.is_default), None)
            if default is not None:
                return True, f"Using system default output: '{default.name}' ({default.host_api})"
            return True, "Using system default output"

        match: Optional[AudioDeviceInfo] = None
        if isinstance(device, int):
            match = next((d for d in available if d.index == device), None)
        else:
            needle = str(device).strip().casefold()
            match = next((d for d in available if needle in d.name.casefold()), None)

        if match is None:
            names = ", ".join(f"{d.index}:{d.name} [{d.host_api}]" for d in available)
            self.last_error = (
                f"Output device {device!r} not found. Available: {names or 'none'}"
            )
            self.logger.error(self.last_error)
            return False, self.last_error

        self._output_device = match.index
        self.last_error = None
        self.logger.info(
            f"Output device selected: #{match.index} '{match.name}' "
            f"({match.host_api}, {match.default_sample_rate:.0f} Hz)"
        )
        return True, f"Using '{match.name}' ({match.host_api})"

    def get_output_device(self) -> Optional[int]:
        """Pinned output device index, or None when following the system default."""
        return self._output_device

    def get_output_device_name(self) -> Optional[str]:
        """Name of the pinned output, or None when following the system default."""
        if self._output_device is None:
            return None
        for device in self.list_output_devices():
            if device.index == self._output_device:
                return device.name
        return None

    def _device_sample_rate(self, device_index: Optional[int]) -> Optional[float]:
        """Native/default sample rate of a device, used for rate recovery."""
        sd = self._sounddevice_module
        if sd is None:
            return None
        try:
            target = device_index if device_index is not None else sd.default.device[1]
            info = sd.query_devices(target)
            rate = float(info.get("default_samplerate") or 0.0)
            return rate if rate > 0 else None
        except Exception:
            return None


    def _candidate_rates(self, device_index: Optional[int]) -> List[float]:
        """
        Rates worth trying after a sample-rate rejection.

        WHY: a WASAPI shared endpoint can refuse 44.1 kHz while still reporting
        `default_samplerate == 44100` (its real mix format is 48 kHz), so the
        recovery rate is probed from PortAudio instead of trusting that single
        number. Order: device default, PortAudio's suggested best pair, then the
        common audio rates.
        """
        sd = self._sounddevice_module
        rates: List[float] = []

        native = self._device_sample_rate(device_index)
        if native:
            rates.append(native)

        if sd is not None:
            try:
                target = (
                    device_index if device_index is not None else sd.default.device[1]
                )
                best = sd.available_sample_rates(target)
                if best:
                    rates.extend(float(r) for r in best)
            except Exception:
                pass

        rates.extend([48000.0, 44100.0, 32000.0])

        unique: List[float] = []
        for rate in rates:
            if rate > 0 and rate not in unique:
                unique.append(rate)
        return [r for r in unique if r != float(self.sample_rate)]

    @staticmethod
    def _is_sample_rate_error(message: str) -> bool:
        """
        Detect a PortAudio sample-rate rejection.

        WHY: Windows WASAPI shared-mode endpoints often refuse any rate other
        than their endpoint mix format (typically 48 kHz) while the app renders
        at 44.1 kHz; recognising that error lets us resample instead of dying.
        """
        lowered = (message or "").lower()
        return "sample rate" in lowered or "samplerate" in lowered

    def _resample_to(self, audio: np.ndarray, target_rate: float) -> np.ndarray:
        """
        Resample rendered audio for one device only.

        Position/mixing math keeps running at `self.sample_rate`; this affects
        the buffer handed to PortAudio, so seeking and the waveform display are
        unaffected by the device's native rate.
        """
        if target_rate <= 0 or target_rate == self.sample_rate or audio.size == 0:
            return audio
        try:
            from math import gcd

            from scipy.signal import resample_poly

            source = int(self.sample_rate)
            target = int(round(target_rate))
            divisor = gcd(source, target) or 1
            resampled = resample_poly(audio, target // divisor, source // divisor, axis=0)
            return np.asarray(resampled, dtype=np.float32)
        except Exception as exc:
            self.logger.warning(f"Resampling to {target_rate:.0f} Hz failed: {exc}")
            return audio

    def _play_array(self, audio: np.ndarray, context: str = "Playback") -> bool:
        """
        Start non-blocking playback on the selected output device.

        WHY this exists: `sounddevice.play()` used to be wrapped in a bare
        `except` that logged and returned, while callers set the player state to
        PLAYING anyway — the UI then showed a running transport with no sound.
        Callers must honour the return value; every failure names the device and
        the reason in `last_error`.

        Recovery order (each attempt logged, never silent): pinned device at the
        rendered rate, pinned device resampled to each plausible device rate,
        then the same for the system default output.
        """
        sd = self._sounddevice_module
        if sd is None:
            self.last_error = "sounddevice/PortAudio unavailable; cannot play audio."
            self.logger.error(self.last_error)
            return False

        candidates: List[Optional[int]] = []
        if self._output_device is not None:
            candidates.append(self._output_device)
        try:
            default_index = sd.default.device[1]
        except Exception:
            default_index = None
        if default_index is not None and default_index not in candidates:
            candidates.append(default_index)
        if not candidates:
            candidates.append(None)

        last_error: Optional[str] = None
        for device in candidates:
            try:
                sd.play(audio, samplerate=self.sample_rate, device=device, blocking=False)
                self.last_error = None
                self.logger.info(
                    f"{context} started on output #{device} @ {self.sample_rate} Hz"
                )
                return True
            except Exception as exc:
                last_error = str(exc)
                self.logger.warning(
                    f"{context} failed on output #{device}: {last_error}"
                )

            if last_error is not None and self._is_sample_rate_error(last_error):
                for rate in self._candidate_rates(device):
                    try:
                        sd.play(
                            self._resample_to(audio, rate),
                            samplerate=rate,
                            device=device,
                            blocking=False,
                        )
                        self.last_error = None
                        self.logger.info(
                            f"{context} started on output #{device} after resampling "
                            f"{self.sample_rate:.0f} -> {rate:.0f} Hz (device rejected "
                            "the requested rate)"
                        )
                        return True
                    except Exception as rate_exc:
                        last_error = str(rate_exc)
                        self.logger.debug(
                            f"{context} rejected {rate:.0f} Hz on output "
                            f"#{device}: {last_error}"
                        )
                        continue

        self.last_error = (
            f"No output device could play audio (last error: {last_error}). "
            "Check that a playback device is connected and not held in WASAPI "
            "exclusive mode."
        )
        self.logger.error(self.last_error)
        return False

    def load_stems(self, stem_files: Dict[str, Path]) -> bool:
        """
        Load stem audio files into memory

        Args:
            stem_files: Dict mapping stem_name -> file_path

        Returns:
            True if successful, False otherwise
        """
        if not stem_files:
            self.logger.warning("No stems to load")
            return False

        self.logger.info(f"Loading {len(stem_files)} stems...")

        try:
            self.stems.clear()
            self.stem_settings.clear()
            max_length = 0
            detected_sample_rate = None

            # Load all stems
            for stem_name, file_path in stem_files.items():
                self.logger.debug(f"Loading stem: {stem_name} from {file_path}")

                # Load audio (ensure float32 for consistent processing)
                audio_data, file_sr = sf.read(
                    str(file_path), always_2d=True, dtype="float32"
                )

                self.logger.info(
                    f"Loaded {stem_name}: sample_rate={file_sr} Hz, "
                    f"shape={audio_data.shape}, duration={audio_data.shape[0]/file_sr:.2f}s"
                )

                # Use first file's sample rate as reference
                if detected_sample_rate is None:
                    detected_sample_rate = file_sr
                    self.sample_rate = file_sr
                    self.logger.info(
                        f"Using sample rate from stems: {self.sample_rate} Hz"
                    )

                # Transpose to (channels, samples)
                audio_data = audio_data.T.astype(np.float32)

                # Resample if needed
                if file_sr != detected_sample_rate:
                    self.logger.warning(
                        f"Stem {stem_name} has different sample rate ({file_sr} vs {detected_sample_rate}). "
                        f"Resampling from {file_sr} to {detected_sample_rate} Hz..."
                    )
                    # Resample using librosa
                    import librosa

                    audio_data = librosa.resample(
                        audio_data,
                        orig_sr=file_sr,
                        target_sr=detected_sample_rate,
                        res_type="kaiser_best",
                    ).astype(np.float32)
                    self.logger.info(
                        f"Resampled {stem_name} to {detected_sample_rate} Hz"
                    )

                # Ensure stereo
                if audio_data.shape[0] == 1:
                    # Mono to stereo
                    audio_data = np.repeat(audio_data, 2, axis=0)
                elif audio_data.shape[0] > 2:
                    # Take first 2 channels
                    audio_data = audio_data[:2, :]

                self.stems[stem_name] = audio_data
                self.stem_settings[stem_name] = StemSettings()

                # Track max length
                max_length = max(max_length, audio_data.shape[1])

                self.logger.debug(
                    f"Loaded {stem_name}: {audio_data.shape[1]} samples, "
                    f"{audio_data.shape[1] / self.sample_rate:.2f}s"
                )

            # Pad all stems to same length
            for stem_name, audio_data in self.stems.items():
                if audio_data.shape[1] < max_length:
                    padding = max_length - audio_data.shape[1]
                    self.stems[stem_name] = np.pad(
                        audio_data,
                        ((0, 0), (0, padding)),
                        mode="constant",
                        constant_values=0,
                    )
                    self.logger.debug(f"Padded {stem_name} with {padding} samples")

            self.duration_samples = max_length
            self.position_samples = 0

            self.logger.info(
                f"Successfully loaded {len(self.stems)} stems. "
                f"Duration: {self.get_duration():.2f}s"
            )

            return True

        except Exception as e:
            self.logger.error(f"Failed to load stems: {e}", exc_info=True)
            self.stems.clear()
            self.stem_settings.clear()
            return False

    def get_duration(self) -> float:
        """Get total duration in seconds"""
        if self.duration_samples == 0:
            return 0.0
        return self.duration_samples / self.sample_rate

    def get_position(self) -> float:
        """Get current position in seconds"""
        with self._position_lock:
            return self.position_samples / self.sample_rate

    def set_position(self, position_seconds: float):
        """
        Seek to position (non-blocking)

        Args:
            position_seconds: Target position in seconds

        WHY: Seeking must not block the GUI thread, especially when sounddevice.stop()
             is called, which can block on some systems. Also allows seeking when stopped
             to enable restarting playback from a different position.
        """
        position_samples = int(position_seconds * self.sample_rate)
        position_samples = max(0, min(position_samples, self.duration_samples))

        # Update position atomically
        with self._position_lock:
            old_position = self.position_samples
            self.position_samples = position_samples
            is_playing = self.state == PlaybackState.PLAYING

        self.logger.info(
            f"Seeked to {position_seconds:.2f}s ({position_samples} samples)"
        )

        # If playing, restart playback from new position (outside lock to prevent deadlock)
        if is_playing and self._sounddevice_module is not None:
            self.logger.debug(
                f"Seeking from {old_position} to {position_samples} samples"
            )
            # Run restart in thread pool to prevent blocking (short-lived task)
            self._thread_pool.submit(self._async_seek_restart)
        # Note: If stopped, position is updated but playback doesn't restart
        # User can click Play to start from the new position

    def _async_seek_restart(self):
        """
        Restart playback after seek (runs in separate thread)

        WHY: sounddevice.stop() can block, so we run this in a separate thread
             to prevent freezing the GUI
        """
        try:
            # Cancel all current playback
            self._cancel_all_actions()
            # Minimal delay to ensure stop completed (reduced from 50ms to 10ms)
            time.sleep(0.01)
            # Start playback from new position
            self._start_playback_from_position()
        except Exception as e:
            self.logger.error(f"Error during async seek restart: {e}", exc_info=True)

    def set_stem_volume(self, stem_name: str, volume: float):
        """Set stem volume (0.0 to 1.0) and apply immediately during playback"""
        if stem_name in self.stem_settings:
            self.stem_settings[stem_name].volume = max(0.0, min(1.0, volume))
            # Restart playback with new mix if currently playing
            self._restart_playback_if_playing()

    def set_stem_mute(self, stem_name: str, is_muted: bool):
        """Set stem mute state and apply immediately during playback"""
        if stem_name in self.stem_settings:
            self.stem_settings[stem_name].is_muted = is_muted
            # Restart playback with new mix if currently playing
            self._restart_playback_if_playing()

    def set_stem_solo(self, stem_name: str, is_solo: bool):
        """Set stem solo state and apply immediately during playback"""
        if stem_name in self.stem_settings:
            self.stem_settings[stem_name].is_solo = is_solo
            # Restart playback with new mix if currently playing
            self._restart_playback_if_playing()

    def set_master_volume(self, volume: float):
        """Set master volume (0.0 to 1.0) and apply immediately during playback"""
        self.master_volume = max(0.0, min(1.0, volume))
        # Restart playback with new mix if currently playing
        self._restart_playback_if_playing()

    def _restart_playback_if_playing(self):
        """Restart playback from current position with new mix (if currently playing)"""
        if self.state == PlaybackState.PLAYING:
            # Stop position update thread temporarily
            self._stop_update.set()
            if self._update_thread and self._update_thread.is_alive():
                self._update_thread.join(timeout=0.5)

            # Stop current playback
            self._cancel_all_actions()

            # Restart from current position with new mix
            self._start_playback_from_position()

            # Restart position update thread
            self._stop_update.clear()
            self._update_thread = threading.Thread(
                target=self._position_update_loop, daemon=True
            )
            self._update_thread.start()

    def is_playback_available(self) -> tuple[bool, str]:
        """
        Check if playback is available

        Returns:
            Tuple of (is_available, error_message)
            - (True, "") if playback is available
            - (False, "error message") if playback is not available
        """
        if not self._sounddevice_module:
            return (
                False,
                "sounddevice library is not available. "
                "Please install it with: pip install sounddevice\n\n"
                "Note: sounddevice requires PortAudio to be installed on your system.\n"
                "On Linux: sudo apt-get install portaudio19-dev\n"
                "On macOS: brew install portaudio\n"
                "On Windows: PortAudio is usually included with sounddevice",
            )

        if not self.stems:
            return (False, "No stems loaded. Please load audio files first.")

        return (True, "")

    def play(self) -> bool:
        """
        Start playback

        Returns:
            True if playback started, False otherwise
        """
        if not self.stems:
            self.logger.warning("No stems loaded, cannot play")
            return False

        if self.state == PlaybackState.PLAYING:
            self.logger.warning("Already playing")
            return False

        if not self._sounddevice_module:
            self.logger.error("sounddevice not available")
            return False

        if self.state == PlaybackState.PAUSED:
            # Resume from pause - restart playback from current position
            self.logger.info("Resuming playback from paused position")
            # Keep current position and start playback
            pass
        else:
            # Start new playback from beginning
            self.position_samples = 0

        # Reset loop mode for normal playback
        # WHY: Normal playback (from Playback tab) should not be in loop mode
        # Loop mode is only for the Looping tab's play_loop_segment()
        self.loop_mode_enabled = False

        try:
            # Start playback from current position (using sounddevice)
            if not self._start_playback_from_position():
                # WHY: never enter PLAYING without a started stream — the UI
                # transport and the position clock must reflect real audio.
                raise RuntimeError(self.last_error or "output device rejected playback")

            self.state = PlaybackState.PLAYING

            if self.state_callback:
                self.state_callback(self.state)

            # Start position update thread
            self._stop_update.clear()
            self._update_thread = threading.Thread(
                target=self._position_update_loop, daemon=True
            )
            self._update_thread.start()

            self.logger.info("Started playback with sounddevice")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start playback: {e}", exc_info=True)
            self.state = PlaybackState.STOPPED
            if self.state_callback:
                self.state_callback(self.state)
            return False

    def _cancel_all_actions(self):
        """Cancel all active playback"""
        if self._sounddevice_module:
            try:
                self._sounddevice_module.stop()
                self.logger.debug("Stopped sounddevice playback")
            except Exception as e:
                self.logger.debug(f"Error stopping sounddevice: {e}")

        self._active_actions.clear()

    def _start_playback_from_position(self) -> bool:
        """Start playback from current position (internal helper) using sounddevice"""
        if self._sounddevice_module is None:
            self.last_error = "sounddevice/PortAudio unavailable; cannot play audio."
            return False

        # Clear previous actions
        self._active_actions.clear()

        with self._position_lock:
            start_sample = self.position_samples

        # Determine end point based on loop mode
        if self.loop_mode_enabled:
            end_sample = self.loop_end_samples
        else:
            end_sample = self.duration_samples

        # Mix stems from current position to end (or loop end)
        mixed_audio = self._mix_stems(start_sample, end_sample)

        if mixed_audio.shape[1] == 0:
            self.last_error = "Nothing to play (empty buffer)."
            self.logger.warning("No audio to play (empty buffer)")
            return False

        # Transpose to (samples, channels) for sounddevice
        chunk_for_playback = mixed_audio.T.astype(np.float32)

        self.logger.info(
            f"Prepared mixed audio: {chunk_for_playback.shape[0]} samples "
            f"({chunk_for_playback.shape[0] / self.sample_rate:.2f}s), "
            f"peak level: {np.max(np.abs(chunk_for_playback)):.3f}"
        )

        return self._play_array(chunk_for_playback, "Playback")

    def _position_update_loop(self):
        """Thread loop for updating position (runs separately from audio)"""
        try:
            # Use perf_counter for higher precision timing
            # WHY: Reduces timing drift compared to time.time()
            start_time = time.perf_counter()
            start_position = self.position_samples

            while not self._stop_update.is_set():
                # Calculate elapsed time with higher precision
                elapsed = time.perf_counter() - start_time
                # Use float calculation, round only at end for better accuracy
                # WHY: Integer truncation accumulates errors over time
                elapsed_samples_float = elapsed * self.sample_rate
                expected_position = int(start_position + elapsed_samples_float)

                with self._position_lock:
                    # Check if position was changed externally (e.g., via seek)
                    # Allow small tolerance for rounding errors
                    position_changed_externally = (
                        abs(self.position_samples - expected_position)
                        > self.sample_rate * 0.1
                    )

                    # Handle loop mode with extended buffer separately
                    if (
                        self.loop_mode_enabled
                        and self._loop_cached_audio is not None
                        and self._loop_single_length > 0
                    ):
                        # Extended buffer mode: don't use normal position tracking
                        # Calculate position within extended buffer
                        extended_buffer_samples = len(self._loop_cached_audio)
                        elapsed_in_extended = expected_position - start_position

                        # Check if extended buffer is exhausted
                        if elapsed_in_extended >= extended_buffer_samples:
                            # Restart the extended buffer
                            self.logger.debug(
                                f"Extended loop buffer exhausted after {elapsed_in_extended} samples, restarting"
                            )

                            # Reset timing
                            start_position = self.loop_start_samples
                            start_time = time.perf_counter()
                            self.position_samples = self.loop_start_samples

                            # Restart playback
                            if not self._play_cached_loop():
                                # WHY: a failed restart must stop the clock;
                                # continuing would move the transport with no
                                # audio behind it.
                                self.logger.error(
                                    f"Loop restart failed: {self.last_error}"
                                )
                                self._stop_update.set()
                                self.state = PlaybackState.STOPPED
                                if self.state_callback:
                                    self.state_callback(self.state)
                                return
                        else:
                            # Wrap position to show correct UI position within single loop
                            pos_in_single = (
                                int(elapsed_in_extended) % self._loop_single_length
                            )
                            self.position_samples = (
                                self.loop_start_samples + pos_in_single
                            )
                    elif position_changed_externally:
                        # Position was changed by seek - reset our timing
                        start_position = self.position_samples
                        start_time = time.perf_counter()
                        self.logger.debug(
                            f"Position update loop detected seek to {self.position_samples} samples, resetting timing"
                        )
                    else:
                        # Update position normally
                        if self.loop_mode_enabled:
                            # In loop mode (no cached audio), clamp to loop boundaries
                            self.position_samples = min(
                                expected_position, self.loop_end_samples
                            )

                            # Check if reached loop end
                            if self.position_samples >= self.loop_end_samples:
                                self.logger.debug(f"Loop end reached, restarting")

                                self.position_samples = self.loop_start_samples
                                start_position = self.loop_start_samples
                                start_time = time.perf_counter()

                                if not self._start_playback_from_position():
                                    self.logger.error(
                                        f"Loop restart failed: {self.last_error}"
                                    )
                                    self._stop_update.set()
                                    self.state = PlaybackState.STOPPED
                                    if self.state_callback:
                                        self.state_callback(self.state)
                                    return
                        else:
                            # Normal mode, clamp to track duration
                            self.position_samples = min(
                                expected_position, self.duration_samples
                            )

                    current_pos = self.position_samples

                    # Check if reached track end (non-loop mode only)
                    if (
                        not self.loop_mode_enabled
                        and current_pos >= self.duration_samples
                    ):
                        self.logger.info("Reached end of audio")
                        self.state = PlaybackState.STOPPED
                        self.position_samples = 0
                        # Call state_callback to notify UI
                        if self.state_callback:
                            try:
                                self.state_callback(self.state)
                            except Exception as e:
                                self.logger.error(
                                    f"Error in state_callback: {e}", exc_info=True
                                )
                        break

                # Call position callback
                if self.position_callback:
                    self.position_callback(self.get_position(), self.get_duration())

                # Update every 10ms for faster loop detection (was 50ms)
                time.sleep(0.01)

        except Exception as e:
            self.logger.error(f"Error in position update loop: {e}", exc_info=True)

    def pause(self):
        """Pause playback"""
        if self.state == PlaybackState.PLAYING:
            # Stop position updates first
            self._stop_update.set()

            # Cancel playback (sounddevice doesn't have pause, so we stop)
            self._cancel_all_actions()

            # Now wait for thread to finish
            if self._update_thread:
                self._update_thread.join(timeout=1.0)

            self.state = PlaybackState.PAUSED

            # Call state callback after thread has finished to avoid deadlock
            if self.state_callback:
                self.state_callback(self.state)

            self.logger.info("Paused playback")

    def stop(self):
        """Stop playback"""
        if self.state in [PlaybackState.PLAYING, PlaybackState.PAUSED]:
            # Stop position updates first
            self._stop_update.set()

            # Cancel playback before waiting for thread
            self._cancel_all_actions()

            # Now wait for thread to finish (it won't call callbacks anymore)
            if self._update_thread:
                self._update_thread.join(timeout=1.0)

            self.state = PlaybackState.STOPPED
            self.position_samples = 0

            # Clear loop mode and cache to free memory
            self.loop_mode_enabled = False
            self._loop_cached_audio = None
            self._loop_single_length = 0

            # Call state callback after thread has finished to avoid deadlock
            if self.state_callback:
                self.state_callback(self.state)

            self.logger.info("Stopped playback")

    def play_loop_segment(
        self, start_sec: float, end_sec: float, repeat: bool = False
    ) -> bool:
        """
        Play a specific loop segment

        Args:
            start_sec: Start time in seconds
            end_sec: End time in seconds
            repeat: If True, loop repeats continuously when reaching end

        Returns:
            True if playback started successfully, False otherwise
        """
        if not self.stems:
            self.logger.warning("No stems loaded, cannot play loop")
            return False

        if not self._sounddevice_module:
            self.logger.error("sounddevice not available")
            return False

        # Convert to samples
        start_sample = int(start_sec * self.sample_rate)
        end_sample = int(end_sec * self.sample_rate)

        # Clamp to valid range
        start_sample = max(0, min(start_sample, self.duration_samples))
        end_sample = max(start_sample, min(end_sample, self.duration_samples))

        if start_sample >= end_sample:
            self.logger.warning(f"Invalid loop segment: {start_sec}s - {end_sec}s")
            return False

        # Stop current playback if playing
        if self.state == PlaybackState.PLAYING:
            self.stop()

        # Set loop mode
        self.loop_mode_enabled = repeat
        self.loop_start_samples = start_sample
        self.loop_end_samples = end_sample
        self.position_samples = start_sample

        self.logger.info(
            f"Playing loop segment: {start_sec:.2f}s - {end_sec:.2f}s "
            f"({'repeat' if repeat else 'once'})"
        )

        # Pre-mix and cache loop audio for fast repeat (avoids re-mixing on each loop)
        # Create extended buffer with multiple repetitions for gapless-ish playback
        if repeat:
            self.logger.info("Pre-mixing loop audio for repeat mode...")
            mixed_audio = self._mix_stems(start_sample, end_sample)
            single_loop = mixed_audio.T.astype(np.float32)

            # Create buffer with multiple repetitions (reduces restart frequency)
            # Each restart of sounddevice.play() has ~10-50ms latency
            num_repetitions = 10  # Play 10 loops before needing to restart
            self._loop_cached_audio = np.tile(single_loop, (num_repetitions, 1))
            self._loop_single_length = len(single_loop)  # Track single loop length

            loop_duration = len(single_loop) / self.sample_rate
            self.logger.info(
                f"Cached loop audio: {len(single_loop)} samples ({loop_duration:.2f}s) "
                f"x {num_repetitions} = {len(self._loop_cached_audio)} total samples"
            )
        else:
            self._loop_cached_audio = None
            self._loop_single_length = 0

        # Start playback from loop start
        try:
            # Use cached loop audio if available (for repeat mode)
            if self._loop_cached_audio is not None:
                started = self._play_cached_loop()
            else:
                started = self._start_playback_from_position()

            if not started:
                raise RuntimeError(self.last_error or "output device rejected loop playback")

            # Update state
            self.state = PlaybackState.PLAYING
            if self.state_callback:
                self.state_callback(self.state)

            # Start position update thread
            self._stop_update.clear()
            self._update_thread = threading.Thread(
                target=self._position_update_loop, daemon=True
            )
            self._update_thread.start()

            return True

        except Exception as e:
            self.logger.error(f"Failed to start loop playback: {e}", exc_info=True)
            return False

    def _play_cached_loop(self) -> bool:
        """Play cached loop audio without re-mixing (for fast loop repeat)"""
        if self._loop_cached_audio is None or self._sounddevice_module is None:
            return False

        return self._play_array(self._loop_cached_audio, "Loop playback")

    def set_loop_mode(
        self, enabled: bool, start_sec: float = 0.0, end_sec: Optional[float] = None
    ):
        """
        Enable or disable loop mode

        Args:
            enabled: Whether to enable loop mode
            start_sec: Loop start time in seconds
            end_sec: Loop end time in seconds (None = end of track)
        """
        self.loop_mode_enabled = enabled

        if enabled:
            self.loop_start_samples = int(start_sec * self.sample_rate)
            if end_sec is None:
                self.loop_end_samples = self.duration_samples
            else:
                self.loop_end_samples = int(end_sec * self.sample_rate)

            # Clamp to valid range
            self.loop_start_samples = max(
                0, min(self.loop_start_samples, self.duration_samples)
            )
            self.loop_end_samples = max(
                self.loop_start_samples,
                min(self.loop_end_samples, self.duration_samples),
            )

            self.logger.info(
                f"Loop mode enabled: {start_sec:.2f}s - "
                f"{(end_sec if end_sec else self.get_duration()):.2f}s"
            )
        else:
            self.logger.info("Loop mode disabled")

    def get_loop_position(self) -> tuple[float, float, float]:
        """
        Get current loop playback position

        Returns:
            Tuple of (position_sec, loop_start_sec, loop_end_sec)
        """
        with self._position_lock:
            position_sec = self.position_samples / self.sample_rate
            loop_start_sec = self.loop_start_samples / self.sample_rate
            loop_end_sec = self.loop_end_samples / self.sample_rate

        return position_sec, loop_start_sec, loop_end_sec

    def _mix_stems(self, start_sample: int, end_sample: int) -> np.ndarray:
        """
        Mix stems with current settings (used for export)

        Args:
            start_sample: Start sample index
            end_sample: End sample index (exclusive)

        Returns:
            Mixed audio (channels, samples)
        """
        # Initialize output
        num_samples = end_sample - start_sample
        mixed = np.zeros((2, num_samples), dtype=np.float32)

        # Check if any stem is solo
        any_solo = any(settings.is_solo for settings in self.stem_settings.values())

        # Mix stems
        for stem_name, audio_data in self.stems.items():
            settings = self.stem_settings[stem_name]

            # Skip if muted
            if settings.is_muted:
                continue

            # Skip if not solo and another stem is solo
            if any_solo and not settings.is_solo:
                continue

            # Extract chunk
            chunk = audio_data[:, start_sample:end_sample]

            # Apply volume
            chunk = chunk * settings.volume

            # Add to mix
            mixed += chunk

        # Apply master volume
        mixed = mixed * self.master_volume

        # Soft clipping to prevent harsh distortion
        peak = np.max(np.abs(mixed))
        if peak > 1.0:
            # Normalize to prevent clipping, with some headroom
            mixed = mixed * (0.95 / peak)

        # Final safety clip (should rarely be needed now)
        mixed = np.clip(mixed, -1.0, 1.0)

        return mixed

    def export_mix(
        self, output_file: Path, file_format: str = "WAV", bit_depth: int = 16
    ) -> bool:
        """
        Export mixed audio to file

        Args:
            output_file: Output file path
            file_format: Audio format ('WAV', 'FLAC')
            bit_depth: Bit depth (16, 24, 32)

        Returns:
            True if successful
        """
        if not self.stems:
            self.logger.error("No stems loaded, cannot export")
            return False

        try:
            self.logger.info(f"Exporting mix to {output_file}")

            # Mix entire audio
            mixed_audio = self._mix_stems(0, self.duration_samples)

            # Transpose to (samples, channels) for soundfile
            audio_to_save = mixed_audio.T

            # Determine subtype
            subtype_map = {16: "PCM_16", 24: "PCM_24", 32: "PCM_32"}
            subtype = subtype_map.get(bit_depth, "PCM_16")

            # Save file
            sf.write(
                str(output_file),
                audio_to_save,
                self.sample_rate,
                subtype=subtype,
                format=file_format,
            )

            self.logger.info(f"Successfully exported mix: {output_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export mix: {e}", exc_info=True)
            return False

    def export_mix_chunked(
        self,
        output_file: Path,
        chunk_length_seconds: float,
        file_format: str = "WAV",
        bit_depth: int = 24,
        common_filename: Optional[str] = None,
    ) -> Optional[list[Path]]:
        """
        Export mixed audio split into chunks

        Args:
            output_file: Base output file path (e.g., "output.wav")
                        Chunks will be saved as "{common_filename}_01.wav", "{common_filename}_02.wav", etc.
            chunk_length_seconds: Target length of each chunk in seconds
            file_format: Audio format ('WAV', 'FLAC')
            bit_depth: Bit depth (16, 24, 32)
            common_filename: Common filename extracted from first loaded stem (e.g., "MySong")

        Returns:
            List of chunk file paths if successful, None on error
        """
        if not self.stems:
            self.logger.error("No stems loaded, cannot export")
            return None

        try:
            self.logger.info(
                f"Exporting mixed audio in {chunk_length_seconds}s chunks to {output_file}"
            )

            # Mix entire audio
            mixed_audio = self._mix_stems(0, self.duration_samples)

            # Use common_filename if provided, otherwise use output_file.stem
            if common_filename:
                # Construct output path with common filename
                output_dir = output_file.parent
                extension = (
                    output_file.suffix
                    if output_file.suffix
                    else f".{file_format.lower()}"
                )
                base_output_path = output_dir / f"{common_filename}{extension}"
            else:
                base_output_path = output_file

            # Export as chunks (mixed_audio is already in (channels, samples) format)
            chunk_paths = export_audio_chunks(
                mixed_audio,
                self.sample_rate,
                base_output_path,
                chunk_length_seconds,
                file_format=file_format,
                bit_depth=bit_depth,
            )

            if chunk_paths:
                self.logger.info(
                    f"Successfully exported {len(chunk_paths)} chunks "
                    f"({chunk_length_seconds}s each)"
                )
                return chunk_paths
            else:
                self.logger.error("No chunks were created")
                return None

        except Exception as e:
            self.logger.error(f"Failed to export chunked mix: {e}", exc_info=True)
            return None

    def export_stems_chunked(
        self,
        output_dir: Path,
        chunk_length_seconds: float,
        file_format: str = "WAV",
        bit_depth: int = 24,
        common_filename: Optional[str] = None,
    ) -> Optional[Dict[str, list[Path]]]:
        """
        Export individual stems split into chunks

        Args:
            output_dir: Directory to save stem chunks
            chunk_length_seconds: Target length of each chunk in seconds
            file_format: Audio format ('WAV', 'FLAC')
            bit_depth: Bit depth (16, 24, 32)
            common_filename: Common filename extracted from first loaded stem (e.g., "MySong")

        Returns:
            Dictionary mapping stem names to lists of chunk file paths,
            or None on error

        Example:
            {
                'vocals': [MySong_vocals_01.wav, MySong_vocals_02.wav, MySong_vocals_03.wav],
                'drums': [MySong_drums_01.wav, MySong_drums_02.wav, MySong_drums_03.wav],
                ...
            }
        """
        if not self.stems:
            self.logger.error("No stems loaded, cannot export")
            return None

        try:
            self.logger.info(
                f"Exporting {len(self.stems)} stems in {chunk_length_seconds}s chunks "
                f"to {output_dir}"
            )

            output_dir.mkdir(parents=True, exist_ok=True)

            all_chunks = {}

            for stem_name, stem_audio in self.stems.items():
                # Get stem settings (volume, mute, solo)
                settings = self.stem_settings.get(stem_name)

                if not settings:
                    # No settings found - use defaults
                    settings = StemSettings()

                if settings.is_muted:
                    self.logger.info(f"Skipping muted stem: {stem_name}")
                    continue

                # Apply volume to stem
                stem_audio_with_volume = stem_audio * settings.volume

                # Generate output path for this stem using common filename
                extension = f".{file_format.lower()}"
                if common_filename:
                    # Format: {common_filename}_{stem_name}.{ext}
                    stem_output_path = (
                        output_dir / f"{common_filename}_{stem_name}{extension}"
                    )
                else:
                    # Fallback to stem name only
                    stem_output_path = output_dir / f"{stem_name}{extension}"

                # Export stem as chunks (with volume applied)
                chunk_paths = export_audio_chunks(
                    stem_audio_with_volume,
                    self.sample_rate,
                    stem_output_path,
                    chunk_length_seconds,
                    file_format=file_format,
                    bit_depth=bit_depth,
                )

                if chunk_paths:
                    all_chunks[stem_name] = chunk_paths
                    self.logger.info(f"Exported {stem_name}: {len(chunk_paths)} chunks")
                else:
                    self.logger.warning(f"No chunks created for stem: {stem_name}")

            if all_chunks:
                total_files = sum(len(chunks) for chunks in all_chunks.values())
                self.logger.info(
                    f"Successfully exported {len(all_chunks)} stems, "
                    f"{total_files} total chunk files"
                )
                return all_chunks
            else:
                self.logger.error("No chunks were created for any stem")
                return None

        except Exception as e:
            self.logger.error(f"Failed to export chunked stems: {e}", exc_info=True)
            return None

    def cleanup(self):
        """Cleanup resources"""
        self.stop()

        # Shutdown thread pool (wait for active tasks to complete)
        if hasattr(self, '_thread_pool'):
            self._thread_pool.shutdown(wait=True, cancel_futures=False)
            self.logger.debug("Thread pool shut down")

        # Stop any ongoing sounddevice playback
        if self._sounddevice_module:
            try:
                self._sounddevice_module.stop()
            except (RuntimeError, AttributeError) as e:
                # Ignore errors during cleanup - sounddevice may not be playing
                logger.debug(f"Error stopping sounddevice during cleanup: {e}")

        self.stems.clear()
        self.stem_settings.clear()


# Global instance
_player: Optional[AudioPlayer] = None


def get_player() -> AudioPlayer:
    """Get global player instance"""
    global _player
    if _player is None:
        _player = AudioPlayer()
    return _player
