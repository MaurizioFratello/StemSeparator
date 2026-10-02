"""
Device enforcement in the separation worker (`core.separation_subprocess`).

WHY these tests exist: `audio_separator.Separator` chooses its own compute
device inside the constructor and offered no override, so the worker accepted a
`device` parameter and ignored it — a user who selected CUDA could receive CPU
inference (or vice versa) with no indication. The fix reassigns the public
attributes after construction and before `load_model()`, and raises instead of
downgrading when a GPU was asked for and cannot be honoured.

These tests inject a fake `torch` module, so no CUDA context is created and the
suite stays cheap on CPU-only machines.
"""

import sys
import json
import subprocess
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from core.separation_subprocess import VALID_DEVICES, _enforce_device


class FakeSeparator:
    """Stand-in for `audio_separator.separator.Separator`."""

    def __init__(self):
        self.torch_device = None
        self.torch_device_cpu = None
        self.torch_device_mps = None
        self.onnx_execution_provider = None


class FakeLogger:
    def __init__(self):
        self.infos = []
        self.warnings = []
        self.errors = []

    def info(self, message, *args, **kwargs):
        self.infos.append(message)

    def warning(self, message, *args, **kwargs):
        self.warnings.append(message)

    def error(self, message, *args, **kwargs):
        self.errors.append(message)


def make_fake_torch(cuda_available=True, cuda_build="12.8", mps_available=False):
    """Minimal torch surface used by `_enforce_device`."""
    torch = types.ModuleType("torch")
    torch.__version__ = "2.9.0+cu128" if cuda_build else "2.9.0+cpu"

    def device(spec):
        return f"torch.device({spec!r})"

    torch.device = device
    torch.cuda = types.SimpleNamespace(is_available=lambda: cuda_available)
    torch.version = types.SimpleNamespace(cuda=cuda_build)
    torch.backends = types.SimpleNamespace(
        mps=types.SimpleNamespace(is_available=lambda: mps_available)
    )
    return torch


@pytest.fixture
def fake_torch(request, monkeypatch):
    """Install a fake torch; parameterise through `patch_torch` below."""
    torch = make_fake_torch()
    monkeypatch.setitem(sys.modules, "torch", torch)
    return torch


@pytest.fixture
def separator():
    return FakeSeparator()


def use_torch(monkeypatch, **kwargs):
    monkeypatch.setitem(sys.modules, "torch", make_fake_torch(**kwargs))


def use_providers(providers):
    """Patch the ONNX provider query so tests do not need onnxruntime."""
    return patch(
        "core.separation_subprocess._available_onnx_providers",
        return_value=providers,
    )


class TestCpuRequest:
    def test_cpu_sets_plain_cpu_state(self, separator, fake_torch):
        logger = FakeLogger()
        with use_providers(["CPUExecutionProvider"]):
            used = _enforce_device(separator, "cpu", logger)

        assert used == "cpu"
        assert separator.torch_device == "torch.device('cpu')"
        assert separator.onnx_execution_provider == ["CPUExecutionProvider"]
        assert not logger.warnings, "a plain CPU run must not warn"

    def test_cpu_clears_the_mps_handle(self, separator, fake_torch):
        """`torch_device_mps` must not stay pointing at an accelerator."""
        logger = FakeLogger()
        with use_providers([]):
            _enforce_device(separator, "cpu", logger)
        assert separator.torch_device_mps == "torch.device('cpu')"

    def test_cpu_always_exposes_a_cpu_handle(self, separator, fake_torch):
        logger = FakeLogger()
        with use_providers([]):
            _enforce_device(separator, "cpu", logger)
        assert separator.torch_device_cpu == "torch.device('cpu')"


class TestCudaRequest:
    def test_cuda_used_when_torch_sees_a_gpu(self, separator, monkeypatch):
        use_torch(monkeypatch, cuda_available=True, cuda_build="12.8")
        logger = FakeLogger()
        with use_providers(["CUDAExecutionProvider", "CPUExecutionProvider"]):
            used = _enforce_device(separator, "cuda", logger)

        assert used == "cuda"
        assert separator.torch_device == "torch.device('cuda')"
        assert separator.onnx_execution_provider == [
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ]
        assert any("Device enforced" in line for line in logger.infos)

    def test_no_cuda_build_raises_with_install_hint(self, separator, monkeypatch):
        use_torch(monkeypatch, cuda_available=False, cuda_build=None)
        logger = FakeLogger()
        with use_providers(["CPUExecutionProvider"]):
            with pytest.raises(RuntimeError) as excinfo:
                _enforce_device(separator, "cuda", logger)

        message = str(excinfo.value)
        assert "no CUDA build" in message
        assert "download.pytorch.org" in message, "must tell the user how to fix it"
        assert "PACKAGING.md" in message, "must point at the documented CUDA section"
        assert separator.torch_device is None, "must not half-configure the separator"

    def test_driver_problem_raises_separate_message(self, separator, monkeypatch):
        use_torch(monkeypatch, cuda_available=False, cuda_build="12.8")
        logger = FakeLogger()
        with use_providers(["CPUExecutionProvider"]):
            with pytest.raises(RuntimeError) as excinfo:
                _enforce_device(separator, "cuda", logger)

        assert "nvidia-smi" in str(excinfo.value)

    def test_cpu_only_onnxruntime_is_reported_not_hidden(self, separator, monkeypatch):
        """
        torch on CUDA with a CPU-only onnxruntime must warn explicitly.

        WHY: silently filtering the provider list made MDX-Net run on CPU while
        the UI claimed GPU inference.
        """
        use_torch(monkeypatch, cuda_available=True, cuda_build="12.8")
        logger = FakeLogger()
        with use_providers(["CPUExecutionProvider"]):
            used = _enforce_device(separator, "cuda", logger)

        assert used == "cuda"
        assert separator.torch_device == "torch.device('cuda')"
        assert separator.onnx_execution_provider == ["CPUExecutionProvider"]
        assert len(logger.warnings) == 1
        warning = logger.warnings[0]
        assert "CUDAExecutionProvider" in warning
        assert "audio-separator[gpu]" in warning, "warning must name the fix"


class TestMpsRequest:
    def test_mps_requires_available_backends(self, separator, monkeypatch):
        use_torch(monkeypatch, cuda_available=False, mps_available=False)
        logger = FakeLogger()
        with use_providers(["CPUExecutionProvider"]):
            with pytest.raises(RuntimeError) as excinfo:
                _enforce_device(separator, "mps", logger)
        assert "MPS" in str(excinfo.value)

    def test_mps_sets_both_handles_and_coreml_provider(self, separator, monkeypatch):
        use_torch(monkeypatch, mps_available=True)
        logger = FakeLogger()
        with use_providers(["CoreMLExecutionProvider", "CPUExecutionProvider"]):
            used = _enforce_device(separator, "mps", logger)

        assert used == "mps"
        assert separator.torch_device == "torch.device('mps')"
        assert separator.torch_device_mps == "torch.device('mps')"
        assert separator.onnx_execution_provider[0] == "CoreMLExecutionProvider"

    def test_missing_mps_module_raises(self, separator, monkeypatch):
        torch = make_fake_torch(mps_available=True)
        del torch.backends.mps
        monkeypatch.setitem(sys.modules, "torch", torch)
        logger = FakeLogger()
        with use_providers([]):
            with pytest.raises(RuntimeError):
                _enforce_device(separator, "mps", logger)


class TestInvalidRequest:
    @pytest.mark.parametrize("device", ["gpu", "", "CPU", "tpu", None])
    def test_rejects_unknown_device(self, separator, fake_torch, device):
        logger = FakeLogger()
        with pytest.raises(ValueError) as excinfo:
            _enforce_device(separator, device, logger)
        assert "expected one of" in str(excinfo.value)

    def test_valid_devices_advertises_the_accepted_set(self):
        assert set(VALID_DEVICES) == {"cpu", "cuda", "mps"}


class TestWorkerLaunch:
    """
    Parent side of the worker contract: environment, argv and IPC files.

    WHY: `spawn`ed children inherit the parent environment, so an explicit CPU
    choice must blank `CUDA_VISIBLE_DEVICES` — audio-separator re-detects the
    device inside the worker and has no CPU override parameter. The worker must
    also be addressed by absolute script path with file-based IPC: `cwd` is the
    output directory (so `-m core.separation_subprocess` cannot import `core`),
    and a `--noconsole` Windows build has no usable stdin/stdout at all.
    """

    @staticmethod
    def launch(device, tmp_path, monkeypatch):
        from core.separator import Separator

        sep = Separator()
        captured = {}

        class Launched(Exception):
            """Raised from the fake pipe read to stop after the launch."""

        class FakeProcess:
            returncode = 0

            def communicate(self, input=None, timeout=None):
                raise Launched("stop right after launch")

        def fake_popen(cmd, **kwargs):
            argv = [str(c) for c in cmd]
            captured["cmd"] = argv
            captured.update(kwargs)
            # Snapshot the IPC payloads now: `_run_separation` deletes both
            # files in its `finally`, so they only exist while the worker runs.
            if "--params-file" in argv:
                params_path = Path(argv[argv.index("--params-file") + 1])
                captured["params_path"] = params_path
                captured["params_raw"] = params_path.read_text(encoding="utf-8")
            return FakeProcess()

        # The parent copies os.environ; clear the developer/CI value so the
        # assertions below test the product code rather than the shell that ran
        # pytest.
        monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
        monkeypatch.setattr("core.separator.subprocess.Popen", fake_popen)
        monkeypatch.setattr(sep.device_manager, "set_device", lambda d: True)

        audio = tmp_path / "in.wav"
        audio.write_bytes(b"RIFF....WAVEfmt ")
        out = tmp_path / "out"
        out.mkdir()

        with pytest.raises(Exception):
            sep._run_separation(
                audio, "demucs_4s", out, "fast", device=device
            )
        captured["cwd"] = captured.get("cwd")
        captured["_out"] = out
        return captured

    def test_cpu_choice_hides_cuda_from_the_child(self, tmp_path, monkeypatch):
        captured = self.launch("cpu", tmp_path, monkeypatch)
        assert captured["env"]["CUDA_VISIBLE_DEVICES"] == ""

    def test_gpu_choice_does_not_hide_cuda(self, tmp_path, monkeypatch):
        captured = self.launch("cuda", tmp_path, monkeypatch)
        assert "CUDA_VISIBLE_DEVICES" not in captured["env"], (
            "blanking CUDA_VISIBLE_DEVICES for a GPU run would make the worker "
            "fall back to CPU while the UI claims CUDA"
        )

    def test_worker_is_marked_and_sandboxed(self, tmp_path, monkeypatch):
        captured = self.launch("cpu", tmp_path, monkeypatch)
        assert captured["env"]["STEMSEPARATOR_SUBPROCESS"] == "1"
        assert captured["stdin"] is subprocess.DEVNULL

    def test_worker_addressed_by_absolute_script_path(self, tmp_path, monkeypatch):
        captured = self.launch("cpu", tmp_path, monkeypatch)
        script = captured["cmd"][1] if captured["cmd"][0].endswith("python") else captured["cmd"][0]
        assert script.endswith("separation_subprocess.py")
        assert Path(script).is_absolute(), "cwd is the output dir, so -m cannot work"
        assert "--params-file" in captured["cmd"]

    def test_parameters_travel_in_a_json_file_with_the_device(self, tmp_path, monkeypatch):
        captured = self.launch("cpu", tmp_path, monkeypatch)
        payload = json.loads(captured["params_raw"])
        assert payload["device"] == "cpu"
        assert payload["model_filename"], "the worker needs the concrete weights file"
        assert payload["result_file"], "the worker must know where to write its result"

    def test_worker_runs_in_the_output_directory(self, tmp_path, monkeypatch):
        captured = self.launch("cpu", tmp_path, monkeypatch)
        assert Path(captured["cwd"]) == captured["_out"].resolve() or Path(
            captured["cwd"]
        ) == captured["_out"]

    def test_ipc_files_are_cleaned_up_after_the_run(self, tmp_path, monkeypatch):
        """
        Stale params/result files must not accumulate in the temp directory.

        WHY: they carry per-run tokens; leaving them behind both leaks disk and
        hides the case where a worker crashed before writing its result.
        """
        captured = self.launch("cpu", tmp_path, monkeypatch)
        assert not captured["params_path"].exists(), "params file must be removed"
        result_path = Path(json.loads(captured["params_raw"])["result_file"])
        assert not result_path.exists(), "result file must be removed"
