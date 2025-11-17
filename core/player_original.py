"""
Audio Player - Real-time playback and mixing of separated stems

PURPOSE: Provides real-time audio playback with per-stem volume/mute/solo controls
CONTEXT: Uses soundcard for cross-platform audio output
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
    Real-time audio player with stem mixing capabilities

    Features:
    - Load multiple stems (audio files)
    - Real-time playback with soundcard
    - Per-stem volume, mute, solo
    - Master volume control
    - Position seeking
    - Callbacks for position updates
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

        # Threading
        self.playback_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._position_lock = threading.Lock()  # Lock for thread-safe seeking

        # Callbacks
        self.position_callback: Optional[Callable[[float, float], None]] = None  # (position, duration)
        self.state_callback: Optional[Callable[[PlaybackState], None]] = None

        # Soundcard
        self._soundcard = None
        self._import_soundcard()

        self.logger.info("AudioPlayer initialized")

    def _import_soundcard(self) -> bool:
        """Import soundcard library"""
        try:
            import soundcard as sc
            self._soundcard = sc
            self.logger.info("SoundCard library loaded for playback")
            return True
        except ImportError:
            self.logger.error("SoundCard not installed. Playback will not work.")
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
        Seek to position (thread-safe)

        Args:
            position_seconds: Target position in seconds
        """
        with self._position_lock:
            position_samples = int(position_seconds * self.sample_rate)
            position_samples = max(0, min(position_samples, self.duration_samples))
            self.position_samples = position_samples
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

        if not self._soundcard:
            self.logger.error("SoundCard not available")
            return False

        if self.state == PlaybackState.PAUSED:
            # Resume from pause
            self._pause_event.set()
            self.state = PlaybackState.PLAYING
            if self.state_callback:
                self.state_callback(self.state)
            self.logger.info("Resumed playback")
            return True

        # Start new playback
        self._stop_event.clear()
        self._pause_event.set()
        self.state = PlaybackState.PLAYING

        if self.state_callback:
            self.state_callback(self.state)

        # Start playback thread
        self.playback_thread = threading.Thread(
            target=self._playback_loop,
            daemon=True
        )
        self.playback_thread.start()

        self.logger.info("Started playback")
        return True

    def pause(self):
        """Pause playback"""
        if self.state == PlaybackState.PLAYING:
            self._pause_event.clear()
            self.state = PlaybackState.PAUSED
            if self.state_callback:
                self.state_callback(self.state)
            self.logger.info("Paused playback")

    def stop(self):
        """Stop playback"""
        if self.state in [PlaybackState.PLAYING, PlaybackState.PAUSED]:
            self._stop_event.set()
            self._pause_event.set()  # Wake up if paused

            if self.playback_thread and self.playback_thread.is_alive():
                self.playback_thread.join(timeout=2.0)

            self.state = PlaybackState.STOPPED
            self.position_samples = 0

            if self.state_callback:
                self.state_callback(self.state)

            self.logger.info("Stopped playback")

    def _playback_loop(self):
        """Main playback loop (runs in separate thread)"""
        try:
            # Get default speaker
            speaker = self._soundcard.default_speaker()

            # Buffer size (samples per buffer)
            # Balance between latency and smooth playback
            # At 48kHz: 8192 samples = ~170ms latency
            buffer_size = 8192

            self.logger.info(
                f"Playback started - Sample rate: {self.sample_rate} Hz, "
                f"Buffer size: {buffer_size} samples"
            )

            while not self._stop_event.is_set():
                # Check pause
                self._pause_event.wait()

                if self._stop_event.is_set():
                    break

                # Get current position (thread-safe)
                with self._position_lock:
                    current_pos = self.position_samples

                # Check if reached end
                if current_pos >= self.duration_samples:
                    self.logger.info("Reached end of audio")
                    self._stop_event.set()
                    break

                # Calculate buffer bounds
                end_sample = min(
                    current_pos + buffer_size,
                    self.duration_samples
                )

                # Mix audio
                mixed_audio = self._mix_stems(current_pos, end_sample)

                # Transpose to (samples, channels) for soundcard
                playback_data = mixed_audio.T

                # Play buffer - this blocks until buffer is played
                # CRITICAL: samplerate must match the actual sample rate of the audio
                speaker.play(playback_data, samplerate=self.sample_rate)

                # Update position (thread-safe)
                with self._position_lock:
                    self.position_samples = end_sample

                # Position callback
                if self.position_callback:
                    self.position_callback(self.get_position(), self.get_duration())

            # Playback finished
            self.state = PlaybackState.STOPPED
            self.position_samples = 0

            if self.state_callback:
                self.state_callback(self.state)

            self.logger.debug("Playback loop finished")

        except Exception as e:
            self.logger.error(f"Error in playback loop: {e}", exc_info=True)
            self.state = PlaybackState.STOPPED
            if self.state_callback:
                self.state_callback(self.state)

    def _mix_stems(self, start_sample: int, end_sample: int) -> np.ndarray:
        """
        Mix stems with current settings

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
        # Use tanh for smooth limiting instead of hard clipping
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
