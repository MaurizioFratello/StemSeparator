"""
BeatNet Beat-Service Client

PURPOSE: Python wrapper to invoke the BeatNet beat-service binary
CONTEXT: Runs beat-service as subprocess, handles JSON I/O, timeouts, errors

The beat-service binary is a separate executable built with PyInstaller
from a Python 3.8/3.9 environment (required for BeatNet/numba compatibility).
"""
import sys
import os
import json
import signal
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Literal

from utils.logger import get_logger

logger = get_logger()

# Type definitions
BeatBackend = Literal["cpu", "mps", "cuda", "auto"]


# ============================================================================
# Data Classes (PRD Section 4.3.1)
# ============================================================================

@dataclass
class Beat:
    """A single beat in the track."""
    time: float               # Seconds from track start
    index: int                # Running beat index (0-based)
    bar: Optional[int] = None  # Bar number (1-based), if known
    beat_in_bar: Optional[int] = None  # Position in bar (e.g., 1..4 for 4/4)


@dataclass
class Downbeat:
    """Start of a bar (downbeat)."""
    time: float               # Seconds
    bar: int                  # Bar number (1-based)


@dataclass
class BeatAnalysisResult:
    """Result of BeatNet analysis."""
    tempo: float
    tempo_confidence: float
    time_signature: str
    beats: List[Beat]
    downbeats: List[Downbeat]
    analysis_duration: float
    audio_duration: Optional[float] = None
    backend: Optional[str] = None      # cpu/mps/cuda
    warnings: Optional[List[str]] = None


# ============================================================================
# Exceptions (PRD Section 4.3.2)
# ============================================================================

class BeatServiceError(Exception):
    """General error from beat service."""
    pass


class BeatServiceTimeout(BeatServiceError):
    """Timeout waiting for beat service."""
    pass


class BeatServiceNotFound(BeatServiceError):
    """Beat service binary not found."""
    pass


# ============================================================================
# Binary Discovery
# ============================================================================

def _find_beat_service_binary() -> Optional[Path]:
    """
    Locate the beatnet-service binary.

    Search order:
    1. PyInstaller bundle (sys._MEIPASS)
    2. Development: packaging/beatnet_service/dist/
    3. Resources directory

    Returns:
        Path to binary or None if not found
    """
    binary_name = "beatnet-service"

    search_paths = []

    # 1. PyInstaller bundle (when running as packaged app)
    if hasattr(sys, '_MEIPASS'):
        search_paths.append(Path(sys._MEIPASS) / binary_name)
        search_paths.append(Path(sys._MEIPASS) / "Frameworks" / binary_name)

    # 2. Development: relative to project root
    # Assuming this file is at utils/beat_service_client.py
    project_root = Path(__file__).parent.parent
    search_paths.extend([
        project_root / "packaging" / "beatnet_service" / "dist" / binary_name,
        project_root / "resources" / "beatnet" / binary_name,
    ])

    # 3. Check PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for dir_path in path_dirs:
        search_paths.append(Path(dir_path) / binary_name)

    # Find first existing executable
    for path in search_paths:
        if path.exists() and path.is_file():
            if os.access(path, os.X_OK):
                logger.debug(f"Found beatnet-service at: {path}")
                return path
            else:
                logger.warning(f"Found beatnet-service but not executable: {path}")

    logger.warning("beatnet-service binary not found in search paths")
    return None


def is_beat_service_available() -> bool:
    """
    Check if the beat-service binary is available.

    Returns:
        True if binary exists and is executable
    """
    return _find_beat_service_binary() is not None


# ============================================================================
# Main API (PRD Section 4.3.2)
# ============================================================================

def analyze_beats(
    audio_path: Path,
    *,
    max_duration: Optional[float] = None,
    device: BeatBackend = "auto",
    timeout_seconds: float = 60.0,
) -> BeatAnalysisResult:
    """
    Run beat analysis via BeatNet service subprocess.

    Args:
        audio_path: Path to audio file
        max_duration: Optional limit on analysis duration (seconds)
        device: Compute device ('cpu', 'mps', 'cuda', 'auto')
        timeout_seconds: Maximum time to wait for analysis

    Returns:
        BeatAnalysisResult with tempo, beats, downbeats

    Raises:
        FileNotFoundError: If audio file doesn't exist
        BeatServiceNotFound: If binary not found
        BeatServiceTimeout: If analysis exceeds timeout
        BeatServiceError: For other errors (non-zero exit, invalid JSON)

    Example:
        >>> result = analyze_beats(Path("song.wav"), timeout_seconds=30.0)
        >>> print(f"Tempo: {result.tempo:.1f} BPM")
        >>> print(f"Beats: {len(result.beats)}, Downbeats: {len(result.downbeats)}")
    """
    # Validate input
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Find binary
    binary_path = _find_beat_service_binary()
    if binary_path is None:
        raise BeatServiceNotFound(
            "beatnet-service binary not found. "
            "Build it with: cd packaging/beatnet_service && ./build.sh"
        )

    # Build command
    cmd = [
        str(binary_path),
        "--input", str(audio_path.absolute()),
        "--output", "-",  # stdout
        "--device", device,
    ]

    if max_duration is not None:
        cmd.extend(["--max-duration", str(max_duration)])

    logger.info(f"Starting beat analysis: {audio_path.name}")
    logger.debug(f"Command: {' '.join(cmd)}")

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

        # Log stderr (for debugging)
        if stderr:
            for line in stderr.strip().split('\n'):
                logger.debug(f"[beatnet-service] {line}")

        # Check exit code
        if process.returncode != 0:
            # Try to parse error JSON
            try:
                error_data = json.loads(stdout)
                error_type = error_data.get("error", "UnknownError")
                error_msg = error_data.get("message", "Unknown error")
                raise BeatServiceError(f"{error_type}: {error_msg}")
            except json.JSONDecodeError:
                raise BeatServiceError(
                    f"Beat service failed with code {process.returncode}: {stderr or stdout}"
                )

        # Parse JSON output
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise BeatServiceError(
                f"Invalid JSON from beat service: {e}\nOutput: {stdout[:500]}"
            )

        # Convert to dataclasses
        beats = [
            Beat(
                time=b["time"],
                index=b["index"],
                bar=b.get("bar"),
                beat_in_bar=b.get("beat_in_bar"),
            )
            for b in data.get("beats", [])
        ]

        downbeats = [
            Downbeat(
                time=d["time"],
                bar=d["bar"],
            )
            for d in data.get("downbeats", [])
        ]

        result = BeatAnalysisResult(
            tempo=data["tempo"],
            tempo_confidence=data.get("tempo_confidence", 0.0),
            time_signature=data.get("time_signature", "4/4"),
            beats=beats,
            downbeats=downbeats,
            analysis_duration=data.get("analysis_duration", 0.0),
            audio_duration=data.get("audio_duration"),
            backend=data.get("backend"),
            warnings=data.get("warnings", []),
        )

        logger.info(
            f"Beat analysis complete: {result.tempo:.1f} BPM, "
            f"{len(beats)} beats, {len(downbeats)} downbeats "
            f"({result.analysis_duration:.1f}s on {result.backend})"
        )

        return result

    except subprocess.TimeoutExpired:
        # Kill process on timeout
        if process:
            _terminate_process(process)
        raise BeatServiceTimeout(
            f"Beat analysis timed out after {timeout_seconds}s"
        )

    except BeatServiceError:
        raise

    except Exception as e:
        if process and process.poll() is None:
            _terminate_process(process)
        raise BeatServiceError(f"Unexpected error: {e}")


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
        logger.warning(f"Error terminating beat service process: {e}")

