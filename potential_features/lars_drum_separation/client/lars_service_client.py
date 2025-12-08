"""
LARS Service Client

PURPOSE: Python wrapper to invoke the LARS service binary for drum separation
CONTEXT: Runs lars-service as subprocess, handles JSON I/O, timeouts, errors

The lars-service binary is a separate executable built with PyInstaller
from a Python 3.9/3.10 environment (required for LarsNet compatibility).
"""

import sys
import os
import json
import signal
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Literal, Dict

from utils.logger import get_logger

logger = get_logger()

# Type definitions
DeviceType = Literal["cpu", "mps", "cuda", "auto"]
OutputFormat = Literal["wav", "flac", "mp3"]
StemName = Literal["kick", "snare", "toms", "hihat", "cymbals"]

# Supported stems
SUPPORTED_STEMS: List[StemName] = ["kick", "snare", "toms", "hihat", "cymbals"]


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class DrumStemPaths:
    """Paths to separated drum stems."""

    kick: Optional[Path] = None
    snare: Optional[Path] = None
    toms: Optional[Path] = None
    hihat: Optional[Path] = None
    cymbals: Optional[Path] = None

    def to_dict(self) -> Dict[str, Optional[Path]]:
        """Convert to dictionary."""
        return {
            "kick": self.kick,
            "snare": self.snare,
            "toms": self.toms,
            "hihat": self.hihat,
            "cymbals": self.cymbals,
        }

    def get(self, stem_name: str) -> Optional[Path]:
        """Get stem path by name."""
        return getattr(self, stem_name, None)


@dataclass
class SeparationResult:
    """Result of LARS drum separation."""

    stems: DrumStemPaths
    processing_time: float
    backend: str  # cpu/mps/cuda
    model: str  # Model name (e.g., "LARS")
    wiener_filter: bool
    output_format: str
    sample_rate: int
    warnings: List[str]


# ============================================================================
# Exceptions
# ============================================================================


class LarsServiceError(Exception):
    """General error from LARS service."""

    pass


class LarsServiceTimeout(LarsServiceError):
    """Timeout waiting for LARS service."""

    pass


class LarsServiceNotFound(LarsServiceError):
    """LARS service binary not found."""

    pass


class LarsProcessingError(LarsServiceError):
    """Processing error during drum separation."""

    pass


# ============================================================================
# Binary Discovery
# ============================================================================


def _find_lars_service_binary() -> Optional[Path]:
    """
    Locate the lars-service binary.

    Search order:
    1. PyInstaller bundle (sys._MEIPASS)
    2. Development: packaging/lars_service/dist/
    3. Resources directory
    4. PATH

    Returns:
        Path to binary or None if not found
    """
    binary_name = "lars-service"

    search_paths = []

    # 1. PyInstaller bundle (when running as packaged app)
    if hasattr(sys, "_MEIPASS"):
        search_paths.append(Path(sys._MEIPASS) / binary_name)
        search_paths.append(Path(sys._MEIPASS) / "Frameworks" / binary_name)

    # 2. Development: relative to project root
    # Assuming this file is at utils/lars_service_client.py
    project_root = Path(__file__).parent.parent
    search_paths.extend(
        [
            project_root / "packaging" / "lars_service" / "dist" / binary_name,
            project_root / "resources" / "lars" / binary_name,
        ]
    )

    # 3. Check PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for dir_path in path_dirs:
        search_paths.append(Path(dir_path) / binary_name)

    # Find first existing executable
    for path in search_paths:
        if path.exists() and path.is_file():
            if os.access(path, os.X_OK):
                logger.debug(f"Found lars-service at: {path}")
                return path
            else:
                logger.warning(f"Found lars-service but not executable: {path}")

    logger.warning("lars-service binary not found in search paths")
    return None


def is_lars_service_available() -> bool:
    """
    Check if the lars-service binary is available.

    Returns:
        True if binary exists and is executable
    """
    return _find_lars_service_binary() is not None


# ============================================================================
# Main API
# ============================================================================


def separate_drum_stems(
    input_path: Path,
    output_dir: Path,
    *,
    stems: Optional[List[StemName]] = None,
    device: DeviceType = "auto",
    wiener_filter: bool = False,
    output_format: OutputFormat = "wav",
    sample_rate: int = 44100,
    timeout_seconds: float = 300.0,
) -> SeparationResult:
    """
    Separate drum stems using LARS service subprocess.

    Args:
        input_path: Path to input drum audio file
        output_dir: Directory for output stem files
        stems: List of stems to extract (default: all 5 stems)
        device: Compute device ('cpu', 'mps', 'cuda', 'auto')
        wiener_filter: Enable Wiener filtering for better quality
        output_format: Output audio format ('wav', 'flac', 'mp3')
        sample_rate: Output sample rate in Hz
        timeout_seconds: Maximum time to wait for separation (default: 5 minutes)

    Returns:
        SeparationResult with paths to generated stems

    Raises:
        FileNotFoundError: If input audio file doesn't exist
        LarsServiceNotFound: If binary not found
        LarsServiceTimeout: If separation exceeds timeout
        LarsProcessingError: For processing errors
        LarsServiceError: For other errors

    Example:
        >>> result = separate_drum_stems(
        ...     Path("drums.wav"),
        ...     Path("/tmp/output"),
        ...     stems=["kick", "snare"],
        ...     device="auto",
        ...     timeout_seconds=60.0
        ... )
        >>> print(f"Kick: {result.stems.kick}")
        >>> print(f"Processing time: {result.processing_time:.1f}s")
    """
    # Validate input
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    output_dir = Path(output_dir)

    # Default to all stems if not specified
    if stems is None:
        stems = SUPPORTED_STEMS.copy()

    # Validate stems
    invalid_stems = [s for s in stems if s not in SUPPORTED_STEMS]
    if invalid_stems:
        raise ValueError(
            f"Invalid stem names: {invalid_stems}. " f"Supported: {SUPPORTED_STEMS}"
        )

    # Find binary
    binary_path = _find_lars_service_binary()
    if binary_path is None:
        raise LarsServiceNotFound(
            "lars-service binary not found. "
            "Build it with: cd packaging/lars_service && ./build.sh"
        )

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build command
    cmd = [
        str(binary_path),
        "separate",
        "--input",
        str(input_path.absolute()),
        "--output-dir",
        str(output_dir.absolute()),
        "--stems",
        ",".join(stems),
        "--device",
        device,
        "--format",
        output_format,
        "--sample-rate",
        str(sample_rate),
    ]

    if wiener_filter:
        cmd.append("--wiener-filter")

    logger.info(f"Starting drum separation: {input_path.name}")
    logger.debug(f"Command: {' '.join(cmd)}")
    logger.debug(f"Output directory: {output_dir}")

    process = None
    try:
        # Start subprocess
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for completion with timeout
        stdout, stderr = process.communicate(timeout=timeout_seconds)

        # Log stderr (for debugging/progress)
        if stderr:
            for line in stderr.strip().split("\n"):
                if line:  # Skip empty lines
                    logger.debug(f"[lars-service] {line}")

        # Check exit code
        if process.returncode != 0:
            # Try to parse error JSON
            try:
                error_data = json.loads(stdout)
                error_type = error_data.get("error", "UnknownError")
                error_msg = error_data.get("message", "Unknown error")
                raise LarsProcessingError(f"{error_type}: {error_msg}")
            except json.JSONDecodeError:
                raise LarsServiceError(
                    f"LARS service failed with code {process.returncode}: {stderr or stdout}"
                )

        # Parse JSON output
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise LarsServiceError(
                f"Invalid JSON from LARS service: {e}\nOutput: {stdout[:500]}"
            )

        # Extract stem paths
        stem_paths_dict = data.get("stems", {})
        stem_paths = DrumStemPaths(
            kick=Path(stem_paths_dict["kick"]) if "kick" in stem_paths_dict else None,
            snare=(
                Path(stem_paths_dict["snare"]) if "snare" in stem_paths_dict else None
            ),
            toms=Path(stem_paths_dict["toms"]) if "toms" in stem_paths_dict else None,
            hihat=(
                Path(stem_paths_dict["hihat"]) if "hihat" in stem_paths_dict else None
            ),
            cymbals=(
                Path(stem_paths_dict["cymbals"])
                if "cymbals" in stem_paths_dict
                else None
            ),
        )

        # Build result
        result = SeparationResult(
            stems=stem_paths,
            processing_time=data.get("processing_time", 0.0),
            backend=data.get("backend", "unknown"),
            model=data.get("model", "LARS"),
            wiener_filter=data.get("wiener_filter", False),
            output_format=data.get("output_format", output_format),
            sample_rate=data.get("sample_rate", sample_rate),
            warnings=data.get("warnings", []),
        )

        logger.info(
            f"Drum separation complete: {len(stems)} stems in "
            f"{result.processing_time:.1f}s on {result.backend}"
        )

        return result

    except subprocess.TimeoutExpired:
        # Kill process on timeout
        if process:
            _terminate_process(process)
        raise LarsServiceTimeout(f"Drum separation timed out after {timeout_seconds}s")

    except (LarsServiceError, LarsProcessingError):
        raise

    except Exception as e:
        if process and process.poll() is None:
            _terminate_process(process)
        raise LarsServiceError(f"Unexpected error: {e}")


def _terminate_process(process: subprocess.Popen) -> None:
    """
    Gracefully terminate a subprocess.

    Strategy: SIGINT → wait → SIGTERM → wait → SIGKILL
    """
    try:
        # Try SIGINT first (allows graceful shutdown)
        if sys.platform != "win32":
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=2.0)
                return
            except subprocess.TimeoutExpired:
                pass

        # Try SIGTERM
        process.terminate()
        try:
            process.wait(timeout=2.0)
            return
        except subprocess.TimeoutExpired:
            pass

        # Force kill
        process.kill()
        process.wait(timeout=1.0)

    except Exception as e:
        logger.warning(f"Error terminating lars service process: {e}")
