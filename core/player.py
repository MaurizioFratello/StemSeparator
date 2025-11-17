"""
Audio Player - Real-time playback and mixing of separated stems

PURPOSE: Provides audio playback with per-stem volume/mute/solo controls
CONTEXT: Uses sounddevice for simple, reliable audio playback of pre-loaded audio
MIGRATION: Migrated from rtmixer to sounddevice.play() for simpler implementation
"""
from pathlib import Path
from typing import Optional, Dict, Callable
from dataclasses import dataclass
from enum import Enum
import threading
import time
import numpy as np
import soundfile as sf

from config import RECORDING_SAMPLE_RATE
from utils.logger import get_logger

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
        self.stems: Dict[str, np.ndarray] = {}  # stem_name -> audio_data (channels, samples)
        self.stem_settings: Dict[str, StemSettings] = {}
        self.master_volume: float = 1.0

        # Threading for position updates
        self._position_lock = threading.Lock()
        self._update_thread: Optional[threading.Thread] = None
        self._stop_update = threading.Event()

        # Callbacks
        self.position_callback: Optional[Callable[[float, float], None]] = None  # (position, duration)
        self.state_callback: Optional[Callable[[PlaybackState], None]] = None

        # Sounddevice for playback
        self._sounddevice_module = None
        self._active_actions = []  # Track active playback for cancellation
        self._import_rtmixer()

        self.logger.info("AudioPlayer initialized with sounddevice")

    def _import_rtmixer(self) -> bool:
        """Import sounddevice library for playback"""
        try:
            import sounddevice as sd
            self._sounddevice_module = sd
            self.logger.info("sounddevice library loaded for playback")

            # Log default audio device information
            try:
                default_device = sd.default.device
                self.logger.info(f"sounddevice default devices: input={default_device[0]}, output={default_device[1]}")
                device_info = sd.query_devices(default_device[1])  # [1] is output device
                self.logger.info(f"Default audio output device: '{device_info['name']}'")
                self.logger.info(f"  - Max output channels: {device_info['max_output_channels']}")
                self.logger.info(f"  - Default sample rate: {device_info['default_samplerate']} Hz")
                self.logger.info(f"  - Host API: {sd.query_hostapis(device_info['hostapi'])['name']}")
            except Exception as e:
                self.logger.warning(f"Could not query audio device info: {e}", exc_info=True)

            return True
        except ImportError as e:
            self.logger.warning(f"sounddevice not installed: {e}")
            self.logger.warning("Install with: pip install sounddevice")
            self._sounddevice_module = None
            return False
        except OSError as e:
            # PortAudio not available (common in headless environments)
            self.logger.warning(f"sounddevice initialization failed: {e}")
            self.logger.warning("This is normal in headless environments or without audio devices")
            self._sounddevice_module = None
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
                audio_data, file_sr = sf.read(str(file_path), always_2d=True, dtype='float32')

                self.logger.info(
                    f"Loaded {stem_name}: sample_rate={file_sr} Hz, "
                    f"shape={audio_data.shape}, duration={audio_data.shape[0]/file_sr:.2f}s"
                )

                # Use first file's sample rate as reference
                if detected_sample_rate is None:
                    detected_sample_rate = file_sr
                    self.sample_rate = file_sr
                    self.logger.info(f"Using sample rate from stems: {self.sample_rate} Hz")

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
                        res_type='kaiser_best'
                    ).astype(np.float32)
                    self.logger.info(f"Resampled {stem_name} to {detected_sample_rate} Hz")

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
                        mode='constant',
                        constant_values=0
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
        Seek to position

        Args:
            position_seconds: Target position in seconds
        """
        with self._position_lock:
            position_samples = int(position_seconds * self.sample_rate)
            position_samples = max(0, min(position_samples, self.duration_samples))
            old_position = self.position_samples
            self.position_samples = position_samples

            # If playing, restart playback from new position
            if self.state == PlaybackState.PLAYING and self._sounddevice_module is not None:
                self.logger.debug(f"Seeking from {old_position} to {position_samples} samples")
                # Cancel all current playback
                self._cancel_all_actions()
                # Start playback from new position
                self._start_playback_from_position()

            self.logger.info(f"Seeked to {position_seconds:.2f}s ({position_samples} samples)")

    def set_stem_volume(self, stem_name: str, volume: float):
        """Set stem volume (0.0 to 1.0)"""
        if stem_name in self.stem_settings:
            self.stem_settings[stem_name].volume = max(0.0, min(1.0, volume))

    def set_stem_mute(self, stem_name: str, is_muted: bool):
        """Set stem mute state"""
        if stem_name in self.stem_settings:
            self.stem_settings[stem_name].is_muted = is_muted

    def set_stem_solo(self, stem_name: str, is_solo: bool):
        """Set stem solo state"""
        if stem_name in self.stem_settings:
            self.stem_settings[stem_name].is_solo = is_solo

    def set_master_volume(self, volume: float):
        """Set master volume (0.0 to 1.0)"""
        self.master_volume = max(0.0, min(1.0, volume))

    def is_playback_available(self) -> tuple[bool, str]:
        """
        Check if playback is available

        Returns:
            Tuple of (is_available, error_message)
            - (True, "") if playback is available
            - (False, "error message") if playback is not available
        """
        if not self._sounddevice_module:
            return (False,
                    "sounddevice library is not available. "
                    "Please install it with: pip install sounddevice\n\n"
                    "Note: sounddevice requires PortAudio to be installed on your system.\n"
                    "On Linux: sudo apt-get install portaudio19-dev\n"
                    "On macOS: brew install portaudio\n"
                    "On Windows: PortAudio is usually included with sounddevice")

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

        try:
            # Start playback from current position (using sounddevice)
            self._start_playback_from_position()

            self.state = PlaybackState.PLAYING

            if self.state_callback:
                self.state_callback(self.state)

            # Start position update thread
            self._stop_update.clear()
            self._update_thread = threading.Thread(
                target=self._position_update_loop,
                daemon=True
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

    def _start_playback_from_position(self):
        """Start playback from current position (internal helper) using sounddevice"""
        if self._sounddevice_module is None:
            return

        # Clear previous actions
        self._active_actions.clear()

        with self._position_lock:
            start_sample = self.position_samples

        # Mix all stems from current position to end
        mixed_audio = self._mix_stems(start_sample, self.duration_samples)

        if mixed_audio.shape[1] == 0:
            self.logger.warning("No audio to play (empty buffer)")
            return

        # Transpose to (samples, channels) for sounddevice
        chunk_for_playback = mixed_audio.T.astype(np.float32)

        self.logger.info(f"Prepared mixed audio: {chunk_for_playback.shape[0]} samples "
                       f"({chunk_for_playback.shape[0] / self.sample_rate:.2f}s), "
                       f"peak level: {np.max(np.abs(chunk_for_playback)):.3f}")

        # Use sounddevice.play() for simple playback (non-blocking)
        try:
            sd = self._sounddevice_module

            # Get default output device
            default_device = sd.default.device[1]

            # Play audio using sounddevice (simpler than rtmixer for pre-loaded audio)
            sd.play(
                chunk_for_playback,
                samplerate=self.sample_rate,
                device=default_device,
                blocking=False  # Non-blocking to allow UI updates
            )

            self.logger.info(f"Started playback with sounddevice.play() on device #{default_device}")

        except Exception as e:
            self.logger.error(f"Failed to play via sounddevice: {e}", exc_info=True)

    def _position_update_loop(self):
        """Thread loop for updating position (runs separately from audio)"""
        try:
            start_time = time.time()
            start_position = self.position_samples

            while not self._stop_update.is_set():
                # Calculate elapsed time
                elapsed = time.time() - start_time
                elapsed_samples = int(elapsed * self.sample_rate)

                with self._position_lock:
                    self.position_samples = min(
                        start_position + elapsed_samples,
                        self.duration_samples
                    )
                    current_pos = self.position_samples

                    # Check if reached end
                    if current_pos >= self.duration_samples:
                        self.logger.info("Reached end of audio")
                        self.state = PlaybackState.STOPPED
                        self.position_samples = 0
                        # Don't call state_callback from worker thread to avoid deadlock
                        # The callback will be triggered when stop() is called
                        break

                # Call position callback
                if self.position_callback:
                    self.position_callback(self.get_position(), self.get_duration())

                # Update every 50ms
                time.sleep(0.05)

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

            # Call state callback after thread has finished to avoid deadlock
            if self.state_callback:
                self.state_callback(self.state)

            self.logger.info("Stopped playback")

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
        any_solo = any(
            settings.is_solo
            for settings in self.stem_settings.values()
        )

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
        self,
        output_file: Path,
        file_format: str = 'WAV',
        bit_depth: int = 16
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
            subtype_map = {
                16: 'PCM_16',
                24: 'PCM_24',
                32: 'PCM_32'
            }
            subtype = subtype_map.get(bit_depth, 'PCM_16')

            # Save file
            sf.write(
                str(output_file),
                audio_to_save,
                self.sample_rate,
                subtype=subtype,
                format=file_format
            )

            self.logger.info(f"Successfully exported mix: {output_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export mix: {e}", exc_info=True)
            return False

    def cleanup(self):
        """Cleanup resources"""
        self.stop()

        # Stop any ongoing sounddevice playback
        if self._sounddevice_module:
            try:
                self._sounddevice_module.stop()
            except:
                pass

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
