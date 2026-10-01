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

    def __init__(self, use_gpu: Optional[bool] = None, force_device: Optional[str] = None):
        """
        Args:
            use_gpu: None -> `config.USE_GPU`; False -> force CPU regardless of
                     hardware. The "Use GPU if available" setting has to reach
                     the inference path, not just the UI.
            force_device: 'cpu' | 'cuda' | 'mps' to pin the device (settings
                     dialog). An unavailable device does NOT silently become
                     CPU; it is reported through `last_error`.
        """
        self.logger = logger
        self._torch = None
        self._current_device = None
        self._device_info: Dict[str, DeviceInfo] = {}
        self._use_gpu = USE_GPU if use_gpu is None else use_gpu
        self._forced = force_device
        self.last_error: Optional[str] = None
        self.selection_reason: str = ""

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
        except OSError as exc:
            # Windows raises OSError ("DLL load failed while importing _C")
            # when the VCRedist or the bundled CUDA runtime DLLs are missing.
            # Without this branch the whole app dies before the GUI appears.
            self.logger.error(
                f"PyTorch failed to load ({exc}). Continuing on CPU. On Windows "
                "this usually means the Visual C++ Redistributable or the CUDA "
                "runtime DLLs are missing - see docs/PACKAGING.md."
            )
            return False

    def _detect_devices(self):
        """Erkennt verfügbare Devices"""
        # CPU ist immer verfügbar
        self._device_info["cpu"] = DeviceInfo(
            name="cpu", available=True, description="CPU (Universal)"
        )

        if not self._import_torch():
            self._device_info["mps"] = DeviceInfo(
                name="mps",
                available=False,
                description="Apple MPS (PyTorch unavailable)",
            )
            self._device_info["cuda"] = DeviceInfo(
                name="cuda",
                available=False,
                description="NVIDIA CUDA (PyTorch unavailable)",
            )
            return

        # Check MPS (Apple Silicon)
        mps_available = False
        if hasattr(self._torch.backends, "mps"):
            try:
                mps_available = bool(self._torch.backends.mps.is_available())
            except Exception as exc:  # pragma: no cover - driver edge case
                self.logger.debug(f"MPS probe failed: {exc}")
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
        try:
            cuda_available = bool(self._torch.cuda.is_available())
        except Exception as exc:  # pragma: no cover - driver edge case
            self.logger.debug(f"CUDA probe failed: {exc}")
            cuda_available = False

        if cuda_available:
            device_count = self._torch.cuda.device_count()
            device_name = (
                self._torch.cuda.get_device_name(0) if device_count > 0 else "Unknown"
            )

            # Get CUDA memory
            try:
                memory_bytes = self._torch.cuda.get_device_properties(0).total_memory
                memory_gb = memory_bytes / (1024**3)
            except (AttributeError, RuntimeError, IndexError) as e:
                # Device may not have accessible memory properties
                self.logger.debug(f"Could not get CUDA memory: {e}")
                memory_gb = None

            built = self._torch.version.cuda or "no CUDA build"
            self._device_info["cuda"] = DeviceInfo(
                name="cuda",
                available=True,
                description=f"NVIDIA CUDA ({device_name}, torch build {built})",
                memory_gb=memory_gb,
            )
            self.logger.info(f"CUDA available: {device_name} (torch build {built})")
        else:
            self._device_info["cuda"] = DeviceInfo(
                name="cuda",
                available=False,
                description=self._cuda_unavailable_description(),
            )
            self.logger.debug("CUDA not available on this system")

    def _cuda_unavailable_description(self) -> str:
        """
        Explain *why* CUDA is unusable so the fix is obvious.

        WHY: on Windows `pip install torch` resolves to the CPU wheel, so the
             usual cause is a CPU-only PyTorch build on a machine that does have
             an NVIDIA GPU. Reporting a bare "not available" sends users in
             circles; naming the missing CUDA wheel ends the support ticket.
        """
        if self._torch is None:
            return "NVIDIA CUDA (PyTorch not installed)"

        cuda_build = getattr(self._torch.version, "cuda", None)
        if cuda_build is None:
            if self._nvidia_gpu_visible():
                return (
                    "NVIDIA GPU detected, but this is a CPU-only PyTorch build "
                    f"({self._torch.__version__}). Install the CUDA wheel - see "
                    "'CUDA Installation' in docs/PACKAGING.md."
                )
            return (
                "NVIDIA CUDA unavailable: CPU-only PyTorch build "
                f"({self._torch.__version__}) and no NVIDIA GPU detected"
            )

        return (
            "NVIDIA CUDA unavailable: PyTorch was built with CUDA "
            f"(cu{cuda_build}) but the driver rejected it - update/enable the "
            "NVIDIA driver and check `nvidia-smi`."
        )

    def _nvidia_gpu_visible(self) -> bool:
        """True when an NVIDIA GPU is present, independent of torch's view."""
        from utils.platform_utils import find_binary, popen_kwargs

        nvidia_smi = find_binary("nvidia-smi")
        if nvidia_smi is None:
            return False
        try:
            import subprocess

            result = subprocess.run(
                [str(nvidia_smi), "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
                **popen_kwargs(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.logger.debug(f"nvidia-smi probe failed: {exc}")
            return False
        return result.returncode == 0 and bool(result.stdout.strip())

    def _preferred_order(self) -> list:
        """
        Accelerator priority for the current OS.

        WHY: Apple Silicon should prefer MPS (CUDA is absent there), while
             Windows/Linux builds should prefer CUDA. Probing an accelerator
             that cannot exist on this OS only delays the first real error.
        """
        from utils.platform_utils import is_macos

        return ["mps", "cuda", "cpu"] if is_macos() else ["cuda", "mps", "cpu"]

    def _select_best_device(self):
        """Wählt das beste verfügbare Device"""
        if self._forced:
            if self.set_device(self._forced):
                return
            self.logger.warning(
                f"Requested device '{self._forced}' unusable ({self.last_error}); "
                "auto-selecting instead"
            )
            self._forced = None

        if not self._use_gpu:
            self._current_device = "cpu"
            self.selection_reason = "GPU disabled in settings"
            self.logger.info("GPU disabled in settings, using CPU")
            return

        for candidate in self._preferred_order():
            info = self._device_info.get(candidate)
            if info is not None and info.available:
                self._current_device = candidate
                self.selection_reason = f"best available accelerator ({candidate})"
                self.logger.info(f"Selected device: {candidate} ({info.description})")
                return

        self._current_device = "cpu"
        self.selection_reason = "no GPU available"
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

        WHY no silent fallback: the previous version flipped the active device
        to CPU while returning True, so a user who selected CUDA could never
        tell that GPU inference never happened. Returning False here lets the
        caller (`Separator._run_separation` -> `ErrorHandler.retry_with_fallback`)
        decide to retry on CPU, which keeps the fallback visible in the log and
        in `SeparationResult.device_used`.

        Args:
            device_name: 'mps', 'cuda', oder 'cpu'

        Returns:
            True wenn das Device aktiv ist, False wenn nicht verfügbar
            (`last_error` erklärt warum)
        """
        device_info = self._device_info.get(device_name)

        if device_info is None:
            self.last_error = f"Unknown device '{device_name}'"
            self.logger.error(self.last_error)
            return False

        if not device_info.available:
            self.last_error = (
                f"Device '{device_name}' not available: {device_info.description}"
            )
            self.logger.error(self.last_error)
            return False

        self._current_device = device_name
        self.selection_reason = "explicitly selected"
        self.last_error = None
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
        from utils.platform_utils import os_name

        info = {
            "os": os_name(),
            "platform": platform.system(),
            "platform_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "current_device": self._current_device,
            "selection_reason": self.selection_reason,
            "last_error": self.last_error,
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
            info["pytorch_cuda_build"] = getattr(self._torch.version, "cuda", None)

        return info


# Globale Instanz
_device_manager: Optional[DeviceManager] = None


def _device_preferences() -> tuple:
    """
    Read (use_gpu, compute_device) from the persisted user settings.

    WHY lazy + defensive: `core` must stay importable without the GUI layer
    (the separation worker runs headless), and `ui.settings_manager` pulls in
    PySide6-free but still optional code — same pattern as
    `core/chunk_processor.py` uses for the chunk length.
    """
    try:
        from ui.settings_manager import get_settings_manager

        settings = get_settings_manager()
        return settings.get_use_gpu(), settings.get_compute_device()
    except Exception:
        return None, "auto"


def get_device_manager() -> DeviceManager:
    """Gibt die globale DeviceManager-Instanz zurück"""
    global _device_manager
    if _device_manager is None:
        use_gpu, compute_device = _device_preferences()
        _device_manager = DeviceManager(
            use_gpu=use_gpu,
            force_device=None if compute_device == "auto" else compute_device,
        )
    return _device_manager


def reload_device_manager() -> DeviceManager:
    """
    Re-create the singleton so a changed GPU/device preference takes effect
    without restarting the app (used by the settings dialog).
    """
    global _device_manager
    _device_manager = None
    return get_device_manager()
