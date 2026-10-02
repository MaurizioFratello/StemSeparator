"""
How persisted settings reach the compute device (`core.device_manager`).

WHY this file exists: the Settings dialog stores `use_gpu` and `compute_device`,
but nothing pinned the contract between those two values and the device the
engine actually uses. `get_device_manager()` is the single place that translates
them, and a wrong mapping there means either a silently ignored GPU toggle or a
pinned device being overwritten by auto-selection.

Availability is always injected, so these tests do not care whether the machine
running them has a GPU: they test the translation, not the hardware.
"""

import pytest

import core.device_manager as device_manager
from core.device_manager import DeviceManager, DeviceInfo


def build(use_gpu, force_device=None, *, cuda=False, mps=False):
    """
    A manager whose accelerator availability is dictated by the test.

    `_detect_devices()` already ran against the real host in __init__, so the
    probe results are replaced and selection is replayed deterministically.
    """
    manager = DeviceManager(use_gpu=use_gpu, force_device=force_device)
    manager._device_info = {
        "cpu": DeviceInfo(name="cpu", available=True, description="Processor"),
        "cuda": DeviceInfo(name="cuda", available=cuda, description="NVIDIA GPU (faked)"),
        "mps": DeviceInfo(name="mps", available=mps, description="Apple Metal (faked)"),
    }
    manager._select_best_device()
    return manager


class TestGpuToggle:
    def test_gpu_disabled_forces_cpu_even_with_cuda_present(self):
        manager = build(use_gpu=False, cuda=True)
        assert manager.get_device() == "cpu"
        assert manager.selection_reason == "GPU disabled in settings"

    def test_gpu_enabled_picks_cuda_when_available(self):
        manager = build(use_gpu=True, cuda=True)
        assert manager.get_device() == "cuda"
        assert "cuda" in manager.selection_reason

    def test_gpu_enabled_without_accelerators_lands_on_cpu(self):
        manager = build(use_gpu=True)
        assert manager.get_device() == "cpu"

    def test_nothing_available_reports_the_degenerate_reason(self):
        """The `no GPU available` branch needs an empty probe map, not cpu."""
        manager = DeviceManager(use_gpu=True)
        manager._device_info = {
            "cpu": DeviceInfo(name="cpu", available=False, description="unavailable"),
            "cuda": DeviceInfo(name="cuda", available=False, description="no GPU"),
            "mps": DeviceInfo(name="mps", available=False, description="no Metal"),
        }
        manager._select_best_device()
        assert manager.get_device() == "cpu"
        assert manager.selection_reason == "no GPU available"


class TestPinnedDevice:
    def test_pinned_cpu_is_respected_while_cuda_is_available(self):
        """`compute_device == 'cpu'` must not be second-guessed by auto-select."""
        manager = build(use_gpu=True, force_device="cpu", cuda=True)
        assert manager.get_device() == "cpu"
        assert manager.selection_reason == "explicitly selected"

    def test_pinned_cuda_keeps_cuda(self):
        manager = build(use_gpu=True, force_device="cuda", cuda=True)
        assert manager.get_device() == "cuda"

    def test_unusable_pin_auto_selects_and_says_why(self):
        """
        Pinning a device this machine lacks must not fail the app or lie.
        WHY: the user asked for CUDA on a machine without it; the manager falls
        back to the best available, but the reason string and the log line are
        what keep that decision auditable instead of silent.
        """
        manager = build(use_gpu=True, force_device="cuda", cuda=False)
        assert manager.get_device() == "cpu"
        assert manager.selection_reason != "explicitly selected", (
            "an unusable pin must not pretend the user got what they asked for"
        )
        assert manager.last_error is not None and "cuda" in manager.last_error

    def test_mps_pin_on_a_non_mac_backend_is_refused_not_adopted(self):
        manager = build(use_gpu=True, force_device="mps", mps=False)
        assert manager.get_device() != "mps"
        assert "mps" in (manager.last_error or "")

    def test_typo_in_settings_falls_back_to_auto(self):
        manager = build(use_gpu=True, force_device="gpupro", cuda=True)
        assert manager.get_device() == "cuda"
        assert "Unknown device" in manager.last_error


class TestPreferenceTranslation:
    @pytest.fixture(autouse=True)
    def isolate_singleton(self):
        device_manager._device_manager = None
        yield
        device_manager._device_manager = None

    def patch_settings(self, monkeypatch, use_gpu, compute_device):
        import ui.settings_manager as settings_module

        class FakeSettings:
            def get_use_gpu(self):
                return use_gpu

            def get_compute_device(self):
                return compute_device

        monkeypatch.setattr(
            settings_module, "get_settings_manager", lambda: FakeSettings()
        )

    def capture_ctor(self, monkeypatch):
        captured = {}

        class Sentinel:
            def __init__(self, **kwargs):
                captured.update(kwargs)
                self._current_device = "cpu"

        monkeypatch.setattr(device_manager, "DeviceManager", Sentinel)
        return captured

    def test_auto_means_no_forced_device(self, monkeypatch):
        self.patch_settings(monkeypatch, True, "auto")
        captured = self.capture_ctor(monkeypatch)
        device_manager.get_device_manager()
        assert captured == {"use_gpu": True, "force_device": None}

    def test_explicit_device_is_forwarded_as_a_pin(self, monkeypatch):
        self.patch_settings(monkeypatch, True, "cuda")
        captured = self.capture_ctor(monkeypatch)
        device_manager.get_device_manager()
        assert captured == {"use_gpu": True, "force_device": "cuda"}

    def test_unreadable_settings_degrade_to_defaults(self, monkeypatch):
        """No GUI layer (headless worker) must not break device selection."""
        import ui.settings_manager as settings_module

        def explode():
            raise RuntimeError("PySide6 missing")

        monkeypatch.setattr(settings_module, "get_settings_manager", explode)
        assert device_manager._device_preferences() == (None, "auto")

    def test_reload_picks_up_changed_preferences(self, monkeypatch):
        """The settings dialog calls this so a toggle works without a restart."""
        self.patch_settings(monkeypatch, True, "auto")
        first = device_manager.get_device_manager()
        assert device_manager.get_device_manager() is first, "must be a singleton"
        self.patch_settings(monkeypatch, False, "auto")
        second = device_manager.reload_device_manager()
        assert second is not first
        assert second.get_device() == "cpu"
        assert second.selection_reason == "GPU disabled in settings", (
            "the GPU toggle must reach the engine without an app restart"
        )
