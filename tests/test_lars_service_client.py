"""
Unit tests for LARS service client

PURPOSE: Test LARS service client functionality
CONTEXT: Phase 1 basic tests for integration validation
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from utils.lars_service_client import (
    is_lars_service_available,
    separate_drum_stems,
    _find_lars_service_binary,
    LarsServiceNotFound,
    LarsServiceError,
    SUPPORTED_STEMS
)


class TestBinaryDiscovery:
    """Test LARS binary discovery"""

    def test_is_lars_service_available_when_binary_exists(self, tmp_path):
        """Test service availability check when binary exists"""
        # Create a fake binary
        fake_binary = tmp_path / "lars-service"
        fake_binary.write_text("#!/bin/bash\necho test")
        fake_binary.chmod(0o755)

        with patch('utils.lars_service_client._find_lars_service_binary', return_value=fake_binary):
            assert is_lars_service_available() is True

    def test_is_lars_service_available_when_binary_missing(self):
        """Test service availability check when binary is missing"""
        with patch('utils.lars_service_client._find_lars_service_binary', return_value=None):
            assert is_lars_service_available() is False


class TestSeparation:
    """Test drum separation functionality"""

    def test_separate_raises_error_when_input_missing(self, tmp_path):
        """Test separation fails when input file doesn't exist"""
        input_file = tmp_path / "nonexistent.wav"
        output_dir = tmp_path / "output"

        with pytest.raises(FileNotFoundError):
            separate_drum_stems(
                input_path=input_file,
                output_dir=output_dir
            )

    def test_separate_raises_error_when_binary_not_found(self, tmp_path):
        """Test separation fails when LARS binary not found"""
        # Create input file
        input_file = tmp_path / "drums.wav"
        input_file.write_bytes(b"RIFF")  # Fake WAV header
        output_dir = tmp_path / "output"

        with patch('utils.lars_service_client._find_lars_service_binary', return_value=None):
            with pytest.raises(LarsServiceNotFound):
                separate_drum_stems(
                    input_path=input_file,
                    output_dir=output_dir
                )

    def test_separate_validates_stem_names(self, tmp_path):
        """Test separation validates stem names"""
        input_file = tmp_path / "drums.wav"
        input_file.write_bytes(b"RIFF")
        output_dir = tmp_path / "output"

        fake_binary = tmp_path / "lars-service"
        fake_binary.write_text("#!/bin/bash\necho test")
        fake_binary.chmod(0o755)

        with patch('utils.lars_service_client._find_lars_service_binary', return_value=fake_binary):
            with pytest.raises(ValueError, match="Invalid stem names"):
                separate_drum_stems(
                    input_path=input_file,
                    output_dir=output_dir,
                    stems=["invalid_stem", "another_invalid"]
                )

    def test_separate_creates_output_directory(self, tmp_path):
        """Test separation creates output directory if it doesn't exist"""
        # Create input file
        input_file = tmp_path / "drums.wav"
        input_file.write_bytes(b"RIFF")
        output_dir = tmp_path / "output"

        # Mock binary and subprocess
        fake_binary = tmp_path / "lars-service"
        fake_binary.write_text("#!/bin/bash\necho test")
        fake_binary.chmod(0o755)

        # Mock successful separation
        mock_result = {
            "version": "1.0.0",
            "model": "LARS",
            "backend": "cpu",
            "stems": {
                "kick": str(output_dir / "drums_kick.wav"),
                "snare": str(output_dir / "drums_snare.wav"),
                "toms": str(output_dir / "drums_toms.wav"),
                "hihat": str(output_dir / "drums_hihat.wav"),
                "cymbals": str(output_dir / "drums_cymbals.wav"),
            },
            "processing_time": 1.23,
            "wiener_filter": False,
            "output_format": "wav",
            "sample_rate": 44100,
            "warnings": []
        }

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            __import__('json').dumps(mock_result),
            ""
        )

        with patch('utils.lars_service_client._find_lars_service_binary', return_value=fake_binary):
            with patch('subprocess.Popen', return_value=mock_process):
                result = separate_drum_stems(
                    input_path=input_file,
                    output_dir=output_dir,
                    timeout_seconds=10.0
                )

                # Verify output directory was created
                assert output_dir.exists()
                assert output_dir.is_dir()

                # Verify result
                assert result.processing_time == 1.23
                assert result.backend == "cpu"
                assert result.stems.kick is not None


class TestSupportedStems:
    """Test supported stems configuration"""

    def test_supported_stems_list(self):
        """Test that all expected stems are supported"""
        expected_stems = ["kick", "snare", "toms", "hihat", "cymbals"]
        assert SUPPORTED_STEMS == expected_stems

    def test_all_stems_are_strings(self):
        """Test that all stem names are strings"""
        assert all(isinstance(stem, str) for stem in SUPPORTED_STEMS)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
