"""
Device Manager für GPU/CPU Detection und Management
"""

from __future__ import annotations

import platform
from typing import Optional, Dict
from dataclasses import dataclass

from config import USE_GPU, FALLBACK_TO_CPU
from utils.logger import get_logger

logger = get_logger()


@dataclass
class DeviceInfo:
    """Informationen über ein verfügbares Device"""

    name: str  # 'mps', 'cuda', 'cpu'
    available: bool
    description: str
    memory_gb: Optional[float] = None


class DeviceManager:
    """Verwaltet GPU/CPU Devices für PyTorch"""

    def __init__(self):
        self.logger = logger
        self._torch = None
        self._current_device = None
        self._device_info: Dict[str, DeviceInfo] = {}

        # Initialisiere Device-Info
        self._detect_devices()

        # Wähle bestes Device
        self._select_best_device()

    def _import_torch(self) -> bool:
        """Importiert PyTorch lazy (nur wenn benötigt)"""
        if self._torch is not None:
            return True

        try:
            import torch

            self._torch = torch
            self.logger.info(f"PyTorch {torch.__version__} loaded")
            return True
        except ImportError:
            self.logger.warning("PyTorch not installed. CPU-only mode.")
            return False

    def _detect_devices(self):
        """Erkennt verfügbare Devices"""
        # CPU ist immer verfügbar
        self._device_info["cpu"] = DeviceInfo(
            name="cpu", available=True, description="CPU (Universal)"
        )

        if not self._import_torch():
            return

        # Check MPS (Apple Silicon)
        if hasattr(self._torch.backends, "mps"):
            mps_available = self._torch.backends.mps.is_available()
            self._device_info["mps"] = DeviceInfo(
                name="mps",
                available=mps_available,
                description="Apple Metal Performance Shaders (Apple Silicon GPU)",
            )

            if mps_available:
                self.logger.info("MPS (Apple Silicon GPU) available")
            else:
                self.logger.debug("MPS not available on this system")

        # Check CUDA (NVIDIA)
        cuda_available = self._torch.cuda.is_available()
        if cuda_available:
            device_count = self._torch.cuda.device_count()
            device_name = (
                self._torch.cuda.get_device_name(0) if device_count > 0 else "Unknown"
            )

            # Get CUDA memory
            try:
                memory_bytes = self._torch.cuda.get_device_properties(0).total_memory
                memory_gb = memory_bytes / (1024**3)
            except:
                memory_gb = None

            self._device_info["cuda"] = DeviceInfo(
                name="cuda",
                available=True,
                description=f"NVIDIA CUDA ({device_name})",
                memory_gb=memory_gb,
            )
            self.logger.info(f"CUDA available: {device_name}")
        else:
            self._device_info["cuda"] = DeviceInfo(
                name="cuda", available=False, description="NVIDIA CUDA (Not available)"
            )
            self.logger.debug("CUDA not available on this system")

    def _select_best_device(self):
        """Wählt das beste verfügbare Device"""
        if not USE_GPU:
            self._current_device = "cpu"
            self.logger.info("GPU disabled in config, using CPU")
            return

        # Priorität: MPS > CUDA > CPU
        if self._device_info.get("mps", DeviceInfo("mps", False, "")).available:
            self._current_device = "mps"
            self.logger.info("Selected device: MPS (Apple Silicon GPU)")
        elif self._device_info.get("cuda", DeviceInfo("cuda", False, "")).available:
            self._current_device = "cuda"
            self.logger.info("Selected device: CUDA (NVIDIA GPU)")
        else:
            self._current_device = "cpu"
            self.logger.info("Selected device: CPU (no GPU available)")

    def get_device(self) -> str:
        """
        Gibt das aktuelle Device zurück

        Returns:
            Device string ('mps', 'cuda', oder 'cpu')
        """
        return self._current_device

    def get_torch_device(self):
        """
        Gibt PyTorch Device-Objekt zurück

        Returns:
            torch.device object oder None wenn PyTorch nicht verfügbar
        """
        if self._torch is None:
            return None

        return self._torch.device(self._current_device)

    def is_gpu_available(self) -> bool:
        """Prüft ob ein GPU verfügbar ist"""
        return self._current_device in ["mps", "cuda"]

    def get_device_info(
        self, device_name: Optional[str] = None
    ) -> Optional[DeviceInfo]:
        """
        Gibt Informationen über ein Device zurück

        Args:
            device_name: Name des Devices ('mps', 'cuda', 'cpu')
                        Wenn None, Info über aktuelles Device

        Returns:
            DeviceInfo oder None
        """
        if device_name is None:
            device_name = self._current_device

        return self._device_info.get(device_name)

    def list_available_devices(self) -> list[DeviceInfo]:
        """Gibt Liste aller verfügbaren Devices zurück"""
        return [info for info in self._device_info.values() if info.available]

    def set_device(self, device_name: str) -> bool:
        """
        Setzt das zu verwendende Device

        Args:
            device_name: 'mps', 'cuda', oder 'cpu'

        Returns:
            True wenn erfolgreich, False wenn Device nicht verfügbar
        """
        device_info = self._device_info.get(device_name)

        if device_info is None:
            self.logger.error(f"Unknown device: {device_name}")
            return False

        if not device_info.available:
            self.logger.error(f"Device '{device_name}' not available")

            if FALLBACK_TO_CPU and device_name != "cpu":
                self.logger.warning("Falling back to CPU")
                self._current_device = "cpu"
                return True

            return False

        self._current_device = device_name
        self.logger.info(f"Device set to: {device_name}")
        return True

    def get_available_memory_gb(self) -> Optional[float]:
        """
        Gibt verfügbaren Speicher in GB zurück

        Returns:
            Memory in GB oder None wenn nicht verfügbar
        """
        if self._torch is None:
            return None

        if self._current_device == "cuda" and self._torch.cuda.is_available():
            try:
                # Verfügbarer Speicher = Total - Allocated
                props = self._torch.cuda.get_device_properties(0)
                total_memory = props.total_memory / (1024**3)
                allocated_memory = self._torch.cuda.memory_allocated(0) / (1024**3)
                return total_memory - allocated_memory
            except Exception as e:
                self.logger.debug(f"Could not get CUDA memory: {e}")
                return None

        elif self._current_device == "mps":
            # MPS hat kein direktes Memory-API
            # Schätze basierend auf System-RAM (macOS teilt unified memory)
            try:
                import psutil

                return psutil.virtual_memory().available / (1024**3)
            except ImportError:
                self.logger.debug("psutil not available for memory check")
                return None

        return None

    def clear_cache(self):
        """Leert GPU Cache"""
        if self._torch is None:
            return

        if self._current_device == "cuda" and self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()
            self.logger.debug("CUDA cache cleared")
        elif self._current_device == "mps":
            # MPS hat kein explizites cache clearing
            # PyTorch managed das automatisch
            self.logger.debug("MPS cache management is automatic")

    def get_system_info(self) -> dict:
        """Gibt System-Informationen zurück"""
        info = {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "current_device": self._current_device,
            "devices": {
                name: {
                    "available": dev.available,
                    "description": dev.description,
                    "memory_gb": dev.memory_gb,
                }
                for name, dev in self._device_info.items()
            },
        }

        if self._torch:
            info["pytorch_version"] = self._torch.__version__

        return info


# Globale Instanz
_device_manager: Optional[DeviceManager] = None


def get_device_manager() -> DeviceManager:
    """Gibt die globale DeviceManager-Instanz zurück"""
    global _device_manager
    if _device_manager is None:
        _device_manager = DeviceManager()
    return _device_manager
