"""Offline contracts for BeatNet helper discovery, launch policy, and PyAudio tiers."""

import importlib
import os
import stat
import sys
import types
from pathlib import Path

import pytest

from utils import beat_service_client as client


class FakeInfo:
    """Minimal device description returned by the application device manager."""

    def __init__(self, available, description="unavailable"):
        self.available = available
        self.description = description


class FakeManager:
    """Offline stand-in for the process-wide device manager."""

    def __init__(self, selected="cpu", infos=None):
        self.selected = selected
        self.infos = infos or {}
        self.selection_reason = "test selection"
        self.last_error = "test device error"

    def get_device(self):
        return self.selected

    def get_device_info(self, name):
        return self.infos.get(name)


class FakePipe:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakePopen:
    """Never-spawned process model that records client termination actions."""

    def __init__(self, pid=1234, polls=None):
        self.pid = pid
        self._polls = iter(polls or [None])
        self.stdout = FakePipe()
        self.stderr = FakePipe()
        self.signals = []
        self.killed = False

    def poll(self):
        try:
            return next(self._polls)
        except StopIteration:
            return None

    def send_signal(self, sig):
        self.signals.append(sig)

    def kill(self):
        self.killed = True


class TestBinaryDiscovery:
    def test_binary_names_follow_platform_executable_spelling(self, monkeypatch):
        monkeypatch.setattr(client.platform_utils, "_platform_string", lambda: "win32")
        assert client._binary_names() == ["beatnet-service.exe", "beatnet-service", "beatnet_service.exe", "beatnet_service"]

        monkeypatch.setattr(client.platform_utils, "_platform_string", lambda: "darwin")
        assert client._binary_names() == ["beatnet-service", "beatnet_service"]

        monkeypatch.setattr(client.platform_utils, "_platform_string", lambda: "linux")
        assert client._binary_names() == ["beatnet-service", "beatnet_service"]

    def test_search_dirs_and_binary_precedence(self, monkeypatch, tmp_path):
        bundled = tmp_path / "bundled"
        source = tmp_path / "source"
        path_dir = tmp_path / "path"
        for directory in (bundled, source, path_dir):
            directory.mkdir()
        bundled_binary = bundled / "beatnet-service"
        source_binary = source / "beatnet-service"
        path_binary = path_dir / "beatnet-service"
        for binary in (bundled_binary, source_binary, path_binary):
            binary.write_text("#!/bin/sh\n")
            binary.chmod(binary.stat().st_mode | stat.S_IXUSR)

        monkeypatch.setattr(client, "_binary_search_dirs", lambda: [bundled, source])
        monkeypatch.setattr(client.shutil, "which", lambda name: str(path_binary))
        assert client._find_beat_service_binary() == bundled_binary

        bundled_binary.unlink()
        assert client._find_beat_service_binary() == source_binary

        source_binary.unlink()
        assert client._find_beat_service_binary() == path_binary

    def test_executable_file_rejects_directories_and_nonexecutables(self, monkeypatch, tmp_path):
        monkeypatch.setattr(client.platform_utils, "_platform_string", lambda: "linux")
        directory = tmp_path / "beatnet-service"
        directory.mkdir()
        ordinary_file = tmp_path / "ordinary"
        ordinary_file.write_text("not executable")
        ordinary_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

        assert not client._is_executable_file(directory)
        assert not client._is_executable_file(ordinary_file)

    def test_source_module_launch_is_used_when_no_binary_exists(self, monkeypatch, tmp_path):
        project = tmp_path / "project"
        service = project / "packaging" / "beatnet_service"
        (service / "src").mkdir(parents=True)
        (service / "src" / "__main__.py").write_text("")
        interpreter = tmp_path / "python"
        interpreter.write_text("")

        monkeypatch.setattr(client, "_project_root", lambda: project)
        monkeypatch.setattr(client.platform_utils, "is_frozen", lambda: False)
        monkeypatch.setattr(client, "_find_beat_service_binary", lambda: None)
        monkeypatch.setattr(client.sys, "executable", str(interpreter))

        launch = client._service_launch_spec()
        assert launch == client.BeatServiceLaunch(
            argv=[str(interpreter), "-m", "src"], cwd=service, kind="module", location=service
        )

    def test_availability_depends_on_either_launch_finder(self, monkeypatch, tmp_path):
        binary = tmp_path / "beatnet-service"
        launch = client.BeatServiceLaunch(["python", "-m", "src"], tmp_path, "module", tmp_path)
        monkeypatch.setattr(client, "_find_beat_service_binary", lambda: binary)
        monkeypatch.setattr(client, "_find_beat_service_module", lambda: None)
        assert client.is_beat_service_available()

        monkeypatch.setattr(client, "_find_beat_service_binary", lambda: None)
        monkeypatch.setattr(client, "_find_beat_service_module", lambda: launch)
        assert client.is_beat_service_available()

        monkeypatch.setattr(client, "_find_beat_service_module", lambda: None)
        assert not client.is_beat_service_available()


class TestDevicePolicy:
    def test_available_requested_backend_and_cpu_pin_are_honoured(self, monkeypatch):
        fake_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: True))
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        manager = FakeManager(infos={"cuda": FakeInfo(True), "cpu": FakeInfo(True)})
        monkeypatch.setattr(client, "_device_manager", lambda: manager)

        assert client._select_device("cuda") == "cuda"
        assert client._select_device("cpu") == "cpu"

    def test_unavailable_explicit_backend_never_silently_falls_back(self, monkeypatch):
        fake_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False))
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        monkeypatch.setattr(client, "_device_manager", lambda: FakeManager(infos={"cuda": FakeInfo(False, "CPU-only wheel")}))

        with pytest.raises(client.BeatServiceError, match="CPU-only wheel"):
            client._select_device("cuda")


class TestServiceLaunchAndTermination:
    def test_popen_flags_and_environment_follow_platform(self, monkeypatch):
        monkeypatch.setattr(client.platform_utils, "_platform_string", lambda: "win32")
        monkeypatch.setattr(client.platform_utils, "popen_kwargs_for_console", lambda: {"creationflags": 0x10})
        monkeypatch.setattr(client.platform_utils, "numba_cuda_safe_env", lambda: {"NUMBA_DISABLE_CU_INIT": "1"})
        monkeypatch.setenv("PRESERVED_FOR_TEST", "yes")
        assert client._service_popen_kwargs() == {"creationflags": 0x210}
        assert client._service_env()["NUMBA_DISABLE_CU_INIT"] == "1"
        assert client._service_env()["PRESERVED_FOR_TEST"] == "yes"

        monkeypatch.setattr(client.platform_utils, "_platform_string", lambda: "linux")
        monkeypatch.setattr(client.platform_utils, "popen_kwargs_for_console", lambda: {"start_new_session": True})
        monkeypatch.setattr(client.platform_utils, "numba_cuda_safe_env", lambda: {"NUMBA_DISABLE_CU_INIT": "1"})
        assert client._service_popen_kwargs() == {"start_new_session": True}

    def test_wait_for_exit_times_out_without_spawning(self, monkeypatch):
        process = FakePopen(polls=[None, None])
        times = iter([0.0, 0.0, 1.0])
        monkeypatch.setattr(client.time, "monotonic", lambda: next(times))
        monkeypatch.setattr(client.time, "sleep", lambda _: None)
        assert not client._wait_for_exit(process, 0.5)

    def test_posix_termination_signals_the_process_group(self, monkeypatch):
        process = FakePopen()
        group_signals = []
        monkeypatch.setattr(client.platform_utils, "is_windows", lambda: False)
        monkeypatch.setattr(client.os, "getpgid", lambda pid: 4321)
        monkeypatch.setattr(client.os, "killpg", lambda pgid, sig: group_signals.append((pgid, sig)))
        monkeypatch.setattr(client, "_wait_for_exit", lambda process, timeout: True)
        monkeypatch.setattr(client, "_group_still_has_members", lambda pgid: False)

        client._terminate_process(process)
        assert group_signals == [(4321, client.signal.SIGINT)]
        assert process.stdout.closed and process.stderr.closed

    def test_windows_termination_uses_taskkill_then_kill_when_tree_kill_fails(self, monkeypatch):
        process = FakePopen()
        calls = []
        monkeypatch.setattr(client.platform_utils, "is_windows", lambda: True)
        monkeypatch.setattr(client.os, "kill", lambda pid, sig: (_ for _ in ()).throw(OSError("no console")))
        monkeypatch.setattr(client.shutil, "which", lambda name: r"C:\\Windows\\System32\\taskkill.exe")
        monkeypatch.setattr(client.platform_utils, "popen_kwargs", lambda: {"creationflags": 1})

        def fail_taskkill(argv, **kwargs):
            calls.append((argv, kwargs))
            raise OSError("taskkill unavailable")

        monkeypatch.setattr(client.subprocess, "run", fail_taskkill)
        monkeypatch.setattr(client, "_wait_for_exit", lambda process, timeout: False)

        client._terminate_process(process)
        assert calls[0][0] == [r"C:\\Windows\\System32\\taskkill.exe", "/PID", "1234", "/T", "/F"]
        assert process.killed


class TestPyAudioTiers:
    @staticmethod
    def _load_shim(monkeypatch, import_module):
        service_dir = Path(__file__).resolve().parents[1] / "packaging" / "beatnet_service"
        monkeypatch.syspath_prepend(str(service_dir))
        monkeypatch.delitem(sys.modules, "src.pyaudio", raising=False)
        monkeypatch.delitem(sys.modules, "pyaudio", raising=False)
        monkeypatch.setattr(importlib, "import_module", import_module)
        return importlib.import_module("src.pyaudio")

    def test_offline_stub_reports_real_import_failure_and_rejects_open(self, monkeypatch):
        real_import = importlib.import_module

        def failing_import(name, package=None):
            if name == "pyaudio":
                raise ImportError("PortAudio unavailable")
            return real_import(name, package)

        shim = self._load_shim(monkeypatch, failing_import)
        assert not shim.REALTIME_SUPPORTED
        assert "ImportError: PortAudio unavailable" in shim.OFFLINE_REASON
        with pytest.raises(RuntimeError, match="PortAudio unavailable"):
            shim.PyAudio().open()

    def test_real_pyaudio_module_is_adopted_after_fresh_import(self, monkeypatch):
        real_import = importlib.import_module
        fake_real = types.SimpleNamespace(PyAudio=type("RealPyAudio", (), {}), paFloat32=99, paCustom=7)

        def adopting_import(name, package=None):
            if name == "pyaudio":
                return fake_real
            return real_import(name, package)

        shim = self._load_shim(monkeypatch, adopting_import)
        assert shim.REALTIME_SUPPORTED
        assert shim.OFFLINE_REASON is None
        assert shim.PyAudio is fake_real.PyAudio
        assert shim.paFloat32 == 99
