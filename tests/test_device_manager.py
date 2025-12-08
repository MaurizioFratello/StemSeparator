"""
Unit Tests für Device Manager
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from core.device_manager import DeviceManager, DeviceInfo, get_device_manager


@pytest.mark.unit
class TestDeviceInfo:
    """Tests für DeviceInfo Dataclass"""

    def test_device_info_creation(self):
        """Teste DeviceInfo Erstellung"""
        info = DeviceInfo(
            name="cpu", available=True, description="CPU Device", memory_gb=8.0
        )

        assert info.name == "cpu"
        assert info.available is True
        assert info.description == "CPU Device"
        assert info.memory_gb == 8.0


@pytest.mark.unit
class TestDeviceManager:
    """Tests für Device Manager"""

    def test_initialization_cpu_only(self):
        """Teste Initialisierung mit nur CPU"""
        with patch(
            "core.device_manager.DeviceManager._import_torch", return_value=False
        ):
            dm = DeviceManager()

            assert dm.get_device() == "cpu"
            assert dm.is_gpu_available() is False
            assert "cpu" in dm._device_info

    def test_initialization_with_torch(self):
        """Teste Initialisierung mit PyTorch"""
        mock_torch = MagicMock()
        mock_torch.__version__ = "2.0.0"
        mock_torch.backends.mps.is_available.return_value = False
        mock_torch.cuda.is_available.return_value = False

        dm = DeviceManager()
        dm._torch = mock_torch  # Setze _torch nach Initialisierung
        dm._detect_devices()  # Rufe _detect_devices() erneut auf

        assert "cpu" in dm._device_info
        assert dm._device_info["cpu"].available is True

    def test_detect_mps_available(self):
        """Teste MPS Detection wenn verfügbar"""
        mock_torch = MagicMock()
        mock_torch.backends.mps.is_available.return_value = True
        mock_torch.cuda.is_available.return_value = False

        dm = DeviceManager()
        dm._torch = mock_torch
        dm._detect_devices()

        assert "mps" in dm._device_info
        assert dm._device_info["mps"].available is True

    def test_detect_cuda_available(self):
        """Teste CUDA Detection wenn verfügbar"""
        mock_torch = MagicMock()
        mock_torch.backends.mps.is_available.return_value = False
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.device_count.return_value = 1
        mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 3080"

        props = MagicMock()
        props.total_memory = 10 * (1024**3)  # 10 GB
        mock_torch.cuda.get_device_properties.return_value = props

        dm = DeviceManager()
        dm._torch = mock_torch
        dm._detect_devices()

        assert "cuda" in dm._device_info
        assert dm._device_info["cuda"].available is True
        assert dm._device_info["cuda"].memory_gb == 10.0

    def test_select_best_device_mps(self):
        """Teste Device-Auswahl: MPS wird bevorzugt"""
        dm = DeviceManager()
        dm._device_info["mps"] = DeviceInfo("mps", True, "MPS")
        dm._device_info["cuda"] = DeviceInfo("cuda", True, "CUDA")
        dm._device_info["cpu"] = DeviceInfo("cpu", True, "CPU")

        dm._select_best_device()
        assert dm.get_device() == "mps"

    def test_select_best_device_cuda(self):
        """Teste Device-Auswahl: CUDA wenn kein MPS"""
        dm = DeviceManager()
        dm._device_info["mps"] = DeviceInfo("mps", False, "MPS")
        dm._device_info["cuda"] = DeviceInfo("cuda", True, "CUDA")
        dm._device_info["cpu"] = DeviceInfo("cpu", True, "CPU")

        dm._select_best_device()
        assert dm.get_device() == "cuda"

    def test_select_best_device_cpu_only(self):
        """Teste Device-Auswahl: CPU wenn kein GPU"""
        dm = DeviceManager()
        dm._device_info["mps"] = DeviceInfo("mps", False, "MPS")
        dm._device_info["cuda"] = DeviceInfo("cuda", False, "CUDA")
        dm._device_info["cpu"] = DeviceInfo("cpu", True, "CPU")

        dm._select_best_device()
        assert dm.get_device() == "cpu"

    def test_get_device(self):
        """Teste get_device()"""
        dm = DeviceManager()
        dm._current_device = "cpu"

        assert dm.get_device() == "cpu"

    def test_get_torch_device_no_torch(self):
        """Teste get_torch_device() ohne PyTorch"""
        dm = DeviceManager()
        dm._torch = None

        assert dm.get_torch_device() is None

    def test_get_torch_device_with_torch(self):
        """Teste get_torch_device() mit PyTorch"""
        mock_torch = MagicMock()
        mock_device = Mock()
        mock_torch.device.return_value = mock_device

        dm = DeviceManager()
        dm._torch = mock_torch
        dm._current_device = "cpu"

        device = dm.get_torch_device()
        mock_torch.device.assert_called_once_with("cpu")
        assert device == mock_device

    def test_is_gpu_available_true(self):
        """Teste is_gpu_available() mit GPU"""
        dm = DeviceManager()
        dm._current_device = "mps"

        assert dm.is_gpu_available() is True

    def test_is_gpu_available_false(self):
        """Teste is_gpu_available() ohne GPU"""
        dm = DeviceManager()
        dm._current_device = "cpu"

        assert dm.is_gpu_available() is False

    def test_get_device_info_current(self):
        """Teste get_device_info() für aktuelles Device"""
        dm = DeviceManager()
        dm._current_device = "cpu"
        dm._device_info["cpu"] = DeviceInfo("cpu", True, "CPU")

        info = dm.get_device_info()
        assert info.name == "cpu"

    def test_get_device_info_specific(self):
        """Teste get_device_info() für spezifisches Device"""
        dm = DeviceManager()
        dm._device_info["mps"] = DeviceInfo("mps", True, "MPS")

        info = dm.get_device_info("mps")
        assert info.name == "mps"

    def test_get_device_info_unknown(self):
        """Teste get_device_info() für unbekanntes Device"""
        dm = DeviceManager()

        info = dm.get_device_info("unknown")
        assert info is None

    def test_list_available_devices(self):
        """Teste list_available_devices()"""
        dm = DeviceManager()
        dm._device_info = {
            "cpu": DeviceInfo("cpu", True, "CPU"),
            "mps": DeviceInfo("mps", True, "MPS"),
            "cuda": DeviceInfo("cuda", False, "CUDA"),
        }

        devices = dm.list_available_devices()
        assert len(devices) == 2
        assert all(d.available for d in devices)

    def test_set_device_success(self):
        """Teste set_device() erfolgreich"""
        dm = DeviceManager()
        dm._device_info["mps"] = DeviceInfo("mps", True, "MPS")

        result = dm.set_device("mps")
        assert result is True
        assert dm.get_device() == "mps"

    def test_set_device_unknown(self):
        """Teste set_device() mit unbekanntem Device"""
        dm = DeviceManager()

        result = dm.set_device("unknown")
        assert result is False

    def test_set_device_unavailable_with_fallback(self):
        """Teste set_device() mit nicht verfügbarem Device (mit Fallback)"""
        with patch("core.device_manager.FALLBACK_TO_CPU", True):
            dm = DeviceManager()
            dm._device_info["cuda"] = DeviceInfo("cuda", False, "CUDA")
            dm._device_info["cpu"] = DeviceInfo("cpu", True, "CPU")

            result = dm.set_device("cuda")
            assert result is True
            assert dm.get_device() == "cpu"

    def test_set_device_unavailable_no_fallback(self):
        """Teste set_device() mit nicht verfügbarem Device (ohne Fallback)"""
        with patch("core.device_manager.FALLBACK_TO_CPU", False):
            dm = DeviceManager()
            dm._device_info["cuda"] = DeviceInfo("cuda", False, "CUDA")

            result = dm.set_device("cuda")
            assert result is False

    def test_clear_cache_cuda(self):
        """Teste clear_cache() für CUDA"""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        dm = DeviceManager()
        dm._torch = mock_torch
        dm._current_device = "cuda"

        dm.clear_cache()
        mock_torch.cuda.empty_cache.assert_called_once()

    def test_clear_cache_mps(self):
        """Teste clear_cache() für MPS (ist No-Op)"""
        mock_torch = MagicMock()

        dm = DeviceManager()
        dm._torch = mock_torch
        dm._current_device = "mps"

        # Sollte nicht crashen
        dm.clear_cache()

    def test_clear_cache_no_torch(self):
        """Teste clear_cache() ohne PyTorch"""
        dm = DeviceManager()
        dm._torch = None

        # Sollte nicht crashen
        dm.clear_cache()

    def test_get_system_info(self):
        """Teste get_system_info()"""
        dm = DeviceManager()
        dm._current_device = "cpu"
        dm._device_info["cpu"] = DeviceInfo("cpu", True, "CPU")

        info = dm.get_system_info()

        assert "platform" in info
        assert "current_device" in info
        assert "devices" in info
        assert info["current_device"] == "cpu"

    def test_get_system_info_with_torch(self):
        """Teste get_system_info() mit PyTorch"""
        mock_torch = MagicMock()
        mock_torch.__version__ = "2.0.0"

        dm = DeviceManager()
        dm._torch = mock_torch

        info = dm.get_system_info()
        assert "pytorch_version" in info
        assert info["pytorch_version"] == "2.0.0"

    def test_get_available_memory_cuda(self):
        """Teste get_available_memory_gb() für CUDA"""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        props = MagicMock()
        props.total_memory = 10 * (1024**3)  # 10 GB
        mock_torch.cuda.get_device_properties.return_value = props
        mock_torch.cuda.memory_allocated.return_value = 2 * (1024**3)  # 2 GB allocated

        dm = DeviceManager()
        dm._torch = mock_torch
        dm._current_device = "cuda"

        memory = dm.get_available_memory_gb()
        assert memory == pytest.approx(8.0, rel=0.1)  # 10 - 2 = 8 GB

    def test_get_available_memory_no_torch(self):
        """Teste get_available_memory_gb() ohne PyTorch"""
        dm = DeviceManager()
        dm._torch = None

        memory = dm.get_available_memory_gb()
        assert memory is None

    def test_singleton(self):
        """Teste get_device_manager Singleton"""
        dm1 = get_device_manager()
        dm2 = get_device_manager()

        assert dm1 is dm2
        assert isinstance(dm1, DeviceManager)

    def test_import_torch_success(self):
        """Teste _import_torch() bei erfolgreicher Installation"""
        # Dieser Test kann nur laufen wenn torch installiert ist
        try:
            import torch

            dm = DeviceManager()
            result = dm._import_torch()
            assert result is True
            assert dm._torch is not None
        except ImportError:
            pytest.skip("PyTorch not installed")

    def test_import_torch_cached(self):
        """Teste dass _import_torch() gecached wird"""
        dm = DeviceManager()
        dm._torch = "already_loaded"

        result = dm._import_torch()
        assert result is True
        assert dm._torch == "already_loaded"
