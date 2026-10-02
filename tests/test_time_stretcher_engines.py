"""
Engine chain and BPM math for loop export (`core.time_stretcher`).

WHY these tests exist: the macOS releases hard-required `brew install rubberband`
and could die at import time. On Windows/Linux the binary is frequently absent,
so the module must degrade through `pyrubberband` to the librosa phase vocoder —
loudly, never silently, and never by handing back unprocessed audio. The stretch
duration is what a DJ-grade loop depends on, so it is asserted numerically.

No fixture files and no external binaries: the audio is synthesised here, and the
optional engines are substituted, so the suite passes with or without the
Rubberband CLI on PATH.
"""

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from core import time_stretcher as ts

SR = 22050


def make_click_train(seconds: float = 1.0, bpm: float = 120.0, stereo: bool = True):
    """Deterministic 120 BPM click train with a decaying tone body."""
    n = int(seconds * SR)
    ticks = np.zeros(n, dtype=np.float32)
    period = SR * 60.0 / bpm
    for i in range(int(seconds * bpm / 60.0)):
        start = int(i * period)
        if start >= n:
            break
        end = min(start + int(0.01 * SR), n)
        t = np.arange(end - start) / SR
        ticks[start:end] += 0.8 * np.exp(-t * 300) * np.sin(2 * np.pi * 1000 * t)
    body = 0.25 * np.sin(2 * np.pi * 220 * np.arange(n) / SR).astype(np.float32)
    mono = np.clip(ticks + body, -1.0, 1.0).astype(np.float32)
    if not stereo:
        return mono
    return np.stack([mono, np.roll(mono, 32)], axis=1).astype(np.float32)


class TestEngineRegistry:
    def test_librosa_is_always_the_last_resort(self):
        engines = ts.available_engines()
        assert engines[-1] == ts.ENGINE_LIBROSA, (
            "the pure-Python phase vocoder must stay listed: it is the only "
            "engine guaranteed present on a fresh Windows install"
        )

    def test_cli_engine_is_advertised_only_when_the_binary_exists(self, monkeypatch):
        monkeypatch.setattr(ts, "rubberband_binary", lambda: None)
        assert ts.ENGINE_CLI not in ts.available_engines()
        monkeypatch.setattr(ts, "rubberband_binary", lambda: "/usr/bin/rubberband")
        assert ts.available_engines().index(ts.ENGINE_CLI) == 0, (
            "the direct CLI call outranks the pyrubberband wrapper (v0.4.0 "
            "has a stereo temp-file bug)"
        )


class TestBpmMath:
    def test_factor_is_target_over_current(self):
        assert ts.calculate_stretch_factor(104.0, 120.0) == pytest.approx(120 / 104)

    @pytest.mark.parametrize("current,target", [(0, 120), (120, 0), (-100, 120)])
    def test_nonsensical_bpm_is_rejected(self, current, target):
        with pytest.raises(ValueError, match="positive"):
            ts.calculate_stretch_factor(current, target)

    def test_out_of_range_factor_raises_before_any_engine_runs(self, monkeypatch):
        def explode(*args, **kwargs):  # pragma: no cover - must not run
            raise AssertionError("an engine ran with an invalid factor")

        monkeypatch.setattr(ts, "_time_stretch_with_rubberband_cli", explode)
        monkeypatch.setattr(ts, "_time_stretch_with_pyrubberband", explode)
        monkeypatch.setattr(ts, "_time_stretch_with_librosa", explode)
        with pytest.raises(ts.InvalidStretchFactorError):
            ts.time_stretch_audio(make_click_train(), SR, 3.0)

    def test_empty_input_is_refused_rather_than_echoed(self):
        with pytest.raises(ts.ProcessingError, match="empty"):
            ts.time_stretch_audio(np.zeros(0, dtype=np.float32), SR, 1.1)


class TestStretching:
    @pytest.mark.parametrize("factor", [1.25, 0.8])
    def test_duration_matches_the_factor_within_dsp_tolerance(self, factor):
        audio = make_click_train(1.0)
        out = ts.time_stretch_audio(audio, SR, factor)
        want = audio.shape[0] / SR / factor
        got = len(out) / SR
        assert abs(got - want) / want < 0.05, f"{got:.3f}s vs {want:.3f}s"

    @pytest.mark.parametrize("factor", [1.25, 0.8])
    def test_channel_count_and_dtype_survive_the_chain(self, factor):
        audio = make_click_train(0.6)
        out = ts.time_stretch_audio(audio, SR, factor)
        assert out.ndim == 2 and out.shape[1] == 2, "stereo must stay stereo"
        assert out.dtype == np.float32
        assert np.all(np.isfinite(out)), "NaN/Inf would be exported to the user's file"

    def test_mono_input_stays_one_dimensional(self):
        mono = make_click_train(0.5, stereo=False)
        out = ts.time_stretch_audio(mono, SR, 1.1)
        assert out.ndim == 1, (
            "callers index `len(out)` as samples; promoting mono to 2-D would "
            "silently change the exported shape"
        )

    def test_the_engine_that_ran_is_logged(self, caplog):
        """Engine changes are never silent: an absent CLI must be visible."""
        with caplog.at_level("INFO"):
            ts.time_stretch_audio(make_click_train(0.4), SR, 1.1)
        text = caplog.text
        assert ts.ENGINE_LIBROSA in text or ts.ENGINE_CLI in text or "engine" in text.lower(), (
            f"expected the winning engine to be named in the log, got: {text[:200]}"
        )


class TestChainFailureReporting:
    @staticmethod
    def _break_all(monkeypatch):
        def broken(engine):
            def impl(*args, **kwargs):
                raise ts.LibraryNotFoundError(f"{engine} is missing")

            return impl

        for engine, name in (
            (ts.ENGINE_CLI, "_time_stretch_with_rubberband_cli"),
            (ts.ENGINE_PYRUBBERBAND, "_time_stretch_with_pyrubberband"),
            (ts.ENGINE_LIBROSA, "_time_stretch_with_librosa"),
        ):
            monkeypatch.setattr(ts, name, broken(engine))

    def test_no_engine_available_is_reported_with_every_attempt(self, monkeypatch):
        """
        A user with no working engine needs the reason and the fix, not silence.

        WHY: returning the input array here would export a loop at the wrong BPM
        and the user would only notice on the dancefloor.
        """
        self._break_all(monkeypatch)
        with pytest.raises(ts.LibraryNotFoundError) as excinfo:
            ts.time_stretch_audio(make_click_train(0.3), SR, 1.1)
        message = str(excinfo.value)
        for engine in (ts.ENGINE_CLI, ts.ENGINE_PYRUBBERBAND, ts.ENGINE_LIBROSA):
            assert engine in message, f"{engine} must appear in the aggregated error"

    def test_first_healthy_engine_short_circuits_the_chain(self, monkeypatch):
        calls = []

        def make(engine, succeed):
            def impl(*args, **kwargs):
                calls.append(engine)
                if succeed:
                    audio = args[0]
                    return audio[: int(len(audio) / 1.1)]
                raise ts.LibraryNotFoundError(f"{engine} unavailable")

            return impl

        monkeypatch.setattr(
            ts, "_time_stretch_with_rubberband_cli", make(ts.ENGINE_CLI, True)
        )
        monkeypatch.setattr(
            ts, "_time_stretch_with_pyrubberband", make(ts.ENGINE_PYRUBBERBAND, False)
        )
        monkeypatch.setattr(ts, "_time_stretch_with_librosa", make(ts.ENGINE_LIBROSA, False))

        out = ts.time_stretch_audio(make_click_train(0.5), SR, 1.1)
        assert calls == [ts.ENGINE_CLI], "a healthy engine must not be followed by fallbacks"
        assert len(out) > 0

    def test_missing_cli_names_the_install_path(self, monkeypatch):
        monkeypatch.setattr(ts, "rubberband_binary", lambda: None)
        with pytest.raises(ts.LibraryNotFoundError) as excinfo:
            ts._time_stretch_with_rubberband_cli(make_click_train(0.2), SR, 1.1, None)
        assert "rubberband" in str(excinfo.value).lower()


class TestImportWithoutOptionalLibraries:
    """
    The module must import on a machine where both optional engines are absent.

    WHY a subprocess: the previous macOS build died at import time here, and the
    only faithful reproduction is a fresh interpreter with `pyrubberband` and
    `librosa` unimportable — patching `builtins.__import__` inside the session
    would poison every other test that lazily imports them.
    """

    SCRIPT = (
        "import builtins, sys\n"
        "real = builtins.__import__\n"
        "def blocked(name, *a, **k):\n"
        "    if name.split('.')[0] in ('pyrubberband', 'librosa'):\n"
        "        raise ImportError('blocked ' + name)\n"
        "    return real(name, *a, **k)\n"
        "builtins.__import__ = blocked\n"
        "from core.time_stretcher import time_stretch_audio, LibraryNotFoundError\n"
        "import numpy as np\n"
        "try:\n"
        "    time_stretch_audio(np.ones(4096, dtype=np.float32), 22050, 1.1)\n"
        "except LibraryNotFoundError as exc:\n"
        "    print('ACTIONABLE:', str(exc)[:120])\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit('expected LibraryNotFoundError')\n"
    )

    def test_import_and_error_are_clean_without_optional_engines(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONPATH=str(root))
        proc = subprocess.run(
            [sys.executable, "-c", self.SCRIPT],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr[-800:]!r}"
        assert "ACTIONABLE:" in proc.stdout, (
            "with every engine missing the caller must still get an actionable "
            f"LibraryNotFoundError, got: {proc.stdout!r}"
        )
