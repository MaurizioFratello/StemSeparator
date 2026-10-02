"""Empty-result handling in the separation worker (core.separation_subprocess).

WHY these tests exist: the worker's original "empty list -> glob the output
dir" rescue search laundered failed runs into phantom successes twice —
first by adopting the *input recording* as a bogus stem (the queue renamed
the user's take!), then by adopting stale-but-tagged outputs of a previous
run, which masked a GPU OOM and short-circuits the CPU fallback chain. An
empty result from audio-separator must now always fail the attempt so the
parent's retry chain re-runs the job on the next strategy.
"""

import sys
import types
from pathlib import Path

import pytest

from core import separation_subprocess as worker


class FakeAudioSeparator:
    """Configurable `audio_separator.separator.Separator` stand-in."""

    instances = []

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.torch_device = None
        self.torch_device_cpu = None
        self.torch_device_mps = None
        self.onnx_execution_provider = None
        self.loaded = None
        FakeAudioSeparator.instances.append(self)

    def load_model(self, model_filename=None):
        self.loaded = model_filename

    def separate(self, audio_path):
        # `result_mode` is set by the fixture: 'crash' returns nothing (the
        # post-error state of a real run), 'write' emits freshly created
        # stem files (the healthy state).
        instance = FakeAudioSeparator.instances[-1]
        if getattr(instance, "result_mode", "crash") == "crash":
            return []
        written = []
        for stem in ("Vocals", "Drums", "Bass", "Other"):
            out = Path(instance.init_kwargs["output_dir"]) / f"take_({stem})_htdemucs.wav"
            out.write_bytes(b"RIFFfresh")
            written.append(str(out))
        return written

    def get_package_distribution(self, package_name):
        # audio-separator's version lookup, exercised by the worker's
        # frozen-bundle patch at separation_subprocess.py:203-217.
        from types import SimpleNamespace

        return SimpleNamespace(version="0.39.1")


def _fake_torch():
    torch = types.ModuleType("torch")
    torch.__version__ = "2.9.0+cpu"
    torch.device = lambda spec: f"torch.device({spec!r})"
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    torch.version = types.SimpleNamespace(cuda=None)
    torch.backends = types.SimpleNamespace(
        mps=types.SimpleNamespace(is_available=lambda: False)
    )
    return torch


@pytest.fixture
def worker_runner(monkeypatch, tmp_path):
    """Run the worker in-process; only the audio-separator itself is faked."""

    monkeypatch.setattr(
        worker, "_require_ffmpeg", lambda logger_sub: None  # gated elsewhere
    )
    monkeypatch.setattr(
        worker, "_available_onnx_providers", lambda: ["CPUExecutionProvider"]
    )
    monkeypatch.setattr(
        worker, "_enforce_device", lambda separator, device, logger_sub: device
    )
    sep_module = types.ModuleType("audio_separator.separator")
    sep_module.Separator = FakeAudioSeparator
    monkeypatch.setitem(sys.modules, "audio_separator.separator", sep_module)
    monkeypatch.setitem(sys.modules, "torch", _fake_torch())
    FakeAudioSeparator.instances.clear()

    def run(audio_file, output_dir, result_mode="crash"):
        monkeypatch.chdir(output_dir)  # the parent sets cwd = output dir
        original_init = FakeAudioSeparator.__init__

        def patched_init(self, **kwargs):
            original_init(self, **kwargs)
            self.result_mode = result_mode

        monkeypatch.setattr(FakeAudioSeparator, "__init__", patched_init)
        return worker.run_separation_subprocess(
            audio_file=audio_file,
            model_id="demucs_4s",
            output_dir=output_dir,
            model_filename="htdemucs.yaml",
            models_dir=tmp_path / "models",
            preset_params={},
            preset_attributes={},
            device="cpu",
        )

    return run


def _make_take(tmp_path):
    take = tmp_path / "take.wav"
    take.write_bytes(b"RIFFfake")
    return take


def _seed_stale_stems(directory):
    for stem in ("Vocals", "Drums", "Bass", "Other"):
        (directory / f"take_({stem}).wav").write_bytes(b"RIFFstale")


class TestEmptyResultIsFailure:
    def test_crash_with_only_input_on_disk_fails_attempt(self, worker_runner, tmp_path):
        """The first live failure: input file must never be adopted as a stem."""
        take = _make_take(tmp_path)  # input sits inside the searched directory

        with pytest.raises(ValueError, match="no output files"):
            worker_runner(take, tmp_path)

        assert take.read_bytes() == b"RIFFfake"  # input untouched, not renamed

    def test_crash_with_stale_tagged_outputs_fails_attempt(
        self, worker_runner, tmp_path
    ):
        """The second live failure: a previous run's correct stems must not
        rescue a crashed attempt — otherwise the CPU fallback never runs."""
        take = _make_take(tmp_path)
        _seed_stale_stems(tmp_path)

        with pytest.raises(ValueError, match="no output files"):
            worker_runner(take, tmp_path)

        for stem in ("Vocals", "Drums", "Bass", "Other"):
            assert (tmp_path / f"take_({stem}).wav").read_bytes() == b"RIFFstale"

    def test_crash_with_untagged_leftovers_fails_attempt(self, worker_runner, tmp_path):
        take = _make_take(tmp_path)
        (tmp_path / "take_mixdown.wav").write_bytes(b"RIFFold")

        with pytest.raises(ValueError, match="no output files"):
            worker_runner(take, tmp_path)

    def test_healthy_run_returns_fresh_tagged_stems(self, worker_runner, tmp_path):
        """Positive control: genuine output still flows through untouched."""
        take = _make_take(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        stems = worker_runner(take, out_dir, result_mode="write")

        assert sorted(stems) == ["Bass", "Drums", "Other", "Vocals"]
        for path in stems.values():
            assert Path(path).read_bytes() == b"RIFFfresh"
