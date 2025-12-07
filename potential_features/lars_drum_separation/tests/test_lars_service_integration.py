"""
Integration tests for LARS service with real audio files

PURPOSE: Test LARS service end-to-end with actual audio files
CONTEXT: Verify stdout redirection fix works with real LarsNet execution
"""
import pytest
import json
import subprocess
import soundfile as sf
from pathlib import Path
from utils.lars_service_client import (
    separate_drum_stems,
    is_lars_service_available,
    LarsServiceNotFound,
    LarsServiceError,
    SUPPORTED_STEMS
)


@pytest.fixture
def real_audio_file():
    """Path to real audio file for testing"""
    audio_path = Path("temp/separated/Disclosure_Tenderly_resampled_44100_(Drums).wav")
    if not audio_path.exists():
        pytest.skip(f"Real audio file not found: {audio_path}")
    return audio_path


@pytest.mark.integration
@pytest.mark.slow
class TestLarsServiceRealAudio:
    """Integration tests with real audio files"""

    @pytest.mark.skipif(
        not is_lars_service_available(),
        reason="LARS service binary not available"
    )
    def test_lars_service_real_audio_separation(self, real_audio_file, tmp_path):
        """
        Test full separation workflow with real audio file.
        
        Verifies:
        - Service exits with code 0
        - stdout contains valid JSON
        - JSON contains all expected fields
        - All 5 stem files are created
        - Stem files are valid audio files
        - No print statements in stdout
        """
        output_dir = tmp_path / "separated_stems"
        
        # Run separation
        result = separate_drum_stems(
            input_path=real_audio_file,
            output_dir=output_dir,
            timeout_seconds=300.0  # 5 minutes for real processing
        )
        
        # Verify result structure
        assert result.processing_time > 0
        assert result.backend in ["cpu", "mps", "cuda"]
        assert result.model == "LARS"
        assert result.output_format == "wav"
        assert result.sample_rate == 44100
        
        # Verify all 5 stems were created
        assert result.stems.kick is not None
        assert result.stems.snare is not None
        assert result.stems.toms is not None
        assert result.stems.hihat is not None
        assert result.stems.cymbals is not None
        
        # Verify stem files exist
        assert result.stems.kick.exists()
        assert result.stems.snare.exists()
        assert result.stems.toms.exists()
        assert result.stems.hihat.exists()
        assert result.stems.cymbals.exists()
        
        # Verify stem files are valid audio files
        for stem_name, stem_path in [
            ("kick", result.stems.kick),
            ("snare", result.stems.snare),
            ("toms", result.stems.toms),
            ("hihat", result.stems.hihat),
            ("cymbals", result.stems.cymbals),
        ]:
            try:
                data, sr = sf.read(str(stem_path))
                assert sr == 44100, f"{stem_name} has wrong sample rate: {sr}"
                assert len(data) > 0, f"{stem_name} is empty"
                assert data.ndim in [1, 2], f"{stem_name} has invalid shape: {data.shape}"
            except Exception as e:
                pytest.fail(f"{stem_name} file is not valid audio: {e}")

    @pytest.mark.skipif(
        not is_lars_service_available(),
        reason="LARS service binary not available"
    )
    def test_lars_service_json_parseable_after_separation(
        self, real_audio_file, tmp_path
    ):
        """
        Test that JSON output is parseable and contains all required fields.
        
        This test directly calls the service binary to verify stdout is clean JSON.
        """
        output_dir = tmp_path / "separated_stems"
        
        # Find the binary
        from utils.lars_service_client import _find_lars_service_binary
        binary_path = _find_lars_service_binary()
        
        if binary_path is None:
            pytest.skip("LARS service binary not found")
        
        # Build command
        cmd = [
            str(binary_path),
            "separate",
            "--input", str(real_audio_file.absolute()),
            "--output-dir", str(output_dir.absolute()),
            "--stems", ",".join(SUPPORTED_STEMS),
            "--device", "auto",
            "--format", "wav",
            "--sample-rate", "44100",
        ]
        
        # Run subprocess and capture stdout/stderr separately
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        stdout, stderr = process.communicate(timeout=300.0)
        
        # Verify exit code is 0 (success)
        assert process.returncode == 0, (
            f"Service failed with code {process.returncode}\n"
            f"stderr: {stderr[:500]}\n"
            f"stdout: {stdout[:500]}"
        )
        
        # Verify stdout contains only JSON (no print statements)
        # Check that stdout starts with JSON (either '{' or whitespace before '{')
        stdout_trimmed = stdout.strip()
        assert stdout_trimmed.startswith("{"), (
            f"stdout does not start with JSON: {stdout[:200]}"
        )
        assert stdout_trimmed.endswith("}"), (
            f"stdout does not end with JSON: {stdout[-200:]}"
        )
        
        # Verify no LarsNet print statements in stdout
        larsnet_prints = [
            "Loading UNet models",
            "Separate drums",
            "Applying Wiener filter",
        ]
        for print_msg in larsnet_prints:
            assert print_msg not in stdout, (
                f"Found LarsNet print statement in stdout: '{print_msg}'\n"
                f"stdout: {stdout[:500]}"
            )
        
        # Verify JSON is parseable
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            pytest.fail(
                f"Failed to parse JSON from stdout: {e}\n"
                f"stdout: {stdout[:500]}"
            )
        
        # Verify all required fields exist
        required_fields = [
            "version",
            "model",
            "backend",
            "stems",
            "processing_time",
            "wiener_filter",
            "output_format",
            "sample_rate",
            "warnings",
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify stems dictionary
        assert isinstance(data["stems"], dict), "stems must be a dictionary"
        assert len(data["stems"]) == 5, f"Expected 5 stems, got {len(data['stems'])}"
        
        # Verify all stem paths are valid
        for stem_name in SUPPORTED_STEMS:
            assert stem_name in data["stems"], f"Missing stem: {stem_name}"
            stem_path = Path(data["stems"][stem_name])
            assert stem_path.exists(), f"Stem file does not exist: {stem_path}"
        
        # Verify stderr contains progress messages (they should be redirected there)
        assert len(stderr) > 0, "stderr should contain progress messages"
        
        # Check for common progress indicators in stderr
        stderr_lower = stderr.lower()
        has_progress = (
            "loading" in stderr_lower or
            "separate" in stderr_lower or
            "%" in stderr or  # Progress bars
            "it/s" in stderr  # tqdm format
        )
        assert has_progress, (
            f"Expected progress messages in stderr, but found: {stderr[:500]}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])

