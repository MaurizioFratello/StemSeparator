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

from config import (
    RECORDING_SAMPLE_RATE,
    RECORDING_CHANNELS,
    RECORDING_FORMAT,
    TEMP_DIR
)
from utils.logger import get_logger
from utils.error_handler import error_handler

logger = get_logger()


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


class Recorder:
    """System Audio Recorder"""

    def __init__(self):
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

        # Callbacks
        self.level_callback: Optional[Callable[[float], None]] = None

        # SoundCard
        self._soundcard = None
        self._import_soundcard()

        self.logger.info("Recorder initialized")

    def _import_soundcard(self) -> bool:
        """Importiert SoundCard Library"""
        try:
            import soundcard as sc
            self._soundcard = sc
            self.logger.info("SoundCard library loaded")
            return True
        except ImportError:
            self.logger.error("SoundCard not installed. Recording will not work.")
            return False

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
                if 'blackhole' in mic.name.lower():
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
        level_callback: Optional[Callable[[float], None]] = None
    ) -> bool:
        """
        Startet Aufnahme

        Args:
            device_name: Name des Recording-Devices (default: BlackHole)
            level_callback: Callback für Audio-Level Updates

        Returns:
            True wenn erfolgreich gestartet
        """
        if self.state == RecordingState.RECORDING:
            self.logger.warning("Already recording")
            return False

        if not self._soundcard:
            self.logger.error("SoundCard not available")
            return False

        # Finde Device
        if device_name:
            self.logger.info(f"Looking for device: '{device_name}'")

            # Suche spezifisches Device
            device = None
            for mic in self._soundcard.all_microphones():
                if device_name == mic.name or device_name in mic.name or mic.name in device_name:
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
                self.logger.error(f"Available microphones: {[mic.name for mic in all_mics]}")
            except:
                pass
            return False

        self.logger.info(f"Starting recording from: {device.name}")

        # Reset State
        self.recorded_chunks = []
        self._stop_event.clear()
        self.level_callback = level_callback
        self.state = RecordingState.RECORDING

        # Starte Recording Thread
        self.recording_thread = threading.Thread(
            target=self._record_loop,
            args=(device,),
            daemon=True
        )
        self.recording_thread.start()

        return True

    def _record_loop(self, device):
        """Recording Loop (läuft in separatem Thread)"""
        try:
            # Blocksize: CoreAudio limits blocksize to 15-512
            # Use maximum allowed blocksize for best performance
            blocksize = 512
            
            # Calculate how many blocks per 0.1 seconds for level updates
            blocks_per_update = int((0.1 * self.sample_rate) / blocksize)
            blocks_per_update = max(1, blocks_per_update)  # At least 1
            
            self.logger.debug(f"Recording with blocksize={blocksize}, blocks_per_update={blocks_per_update}")

            with device.recorder(
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=blocksize
            ) as recorder:

                block_counter = 0
                
                while not self._stop_event.is_set():
                    if self.state != RecordingState.RECORDING:
                        # Pausiert - warte kurz
                        time.sleep(0.1)
                        continue

                    # Nehme Audio-Block auf
                    audio_block = recorder.record(numframes=blocksize)

                    # Speichere Chunk
                    self.recorded_chunks.append(audio_block)

                    # Berechne Audio-Level (RMS) - nur alle blocks_per_update Blocks
                    block_counter += 1
                    if self.level_callback and block_counter >= blocks_per_update:
                        rms = np.sqrt(np.mean(audio_block**2))
                        # Normalisiere auf 0-1 Range (ca.)
                        level = min(rms * 10, 1.0)
                        self.level_callback(level)
                        block_counter = 0

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
        self,
        save_path: Optional[Path] = None
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

            duration = len(audio_data) / self.sample_rate
            peak_level = float(np.max(np.abs(audio_data)))

            self.logger.info(
                f"Recorded {duration:.1f}s, "
                f"peak level: {peak_level:.2f}"
            )

            # Speichere wenn Pfad angegeben
            if save_path:
                save_path = Path(save_path)
                save_path.parent.mkdir(parents=True, exist_ok=True)

                sf.write(
                    str(save_path),
                    audio_data,
                    self.sample_rate
                )

                self.logger.info(f"Recording saved to: {save_path}")

            else:
                # Default: Temp-Verzeichnis
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                save_path = TEMP_DIR / f"recording_{timestamp}.wav"
                save_path.parent.mkdir(parents=True, exist_ok=True)

                sf.write(
                    str(save_path),
                    audio_data,
                    self.sample_rate
                )

                self.logger.info(f"Recording saved to temp: {save_path}")

            # Reset
            self.state = RecordingState.IDLE
            self.recorded_chunks = []

            return RecordingInfo(
                duration_seconds=duration,
                sample_rate=self.sample_rate,
                channels=self.channels,
                file_path=save_path,
                peak_level=peak_level
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

            # Stoppe Thread
            self._stop_event.set()
            self.state = RecordingState.IDLE

            # Warte auf Thread
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=2.0)

            # Lösche Chunks
            self.recorded_chunks = []
            self.logger.info("Recording cancelled")


# Globale Instanz
_recorder: Optional[Recorder] = None


def get_recorder() -> Recorder:
    """Gibt die globale Recorder-Instanz zurück"""
    global _recorder
    if _recorder is None:
        _recorder = Recorder()
    return _recorder


if __name__ == "__main__":
    # Test
    recorder = Recorder()

    print("=== Recorder Test ===")
    print(f"Available devices:")
    for device in recorder.get_available_devices():
        print(f"  - {device}")

    blackhole = recorder.find_blackhole_device()
    if blackhole:
        print(f"\n✓ BlackHole found: {blackhole.name}")
    else:
        print("\n✗ BlackHole not found")
        print("Install with: brew install blackhole-2ch")
