"""
Device Detection for BeatNet Beat-Service

PURPOSE: Turn the client's `--device` request into a PyTorch device that is
         provably usable in *this* process, or refuse it with an explanation.
CONTEXT: The service ships as a standalone PyInstaller binary built from an
         isolated environment, so it cannot import the app's
         `core.device_manager`. The app resolves its policy there and passes a
         concrete device; this module only verifies and reports.

The verification is strict on purpose: an earlier build fell back to "cpu"
whenever a probe failed, which made a CUDA-only-wheel install or a Windows
machine with a broken driver look like "the app just ignores my GPU". A pin
that cannot be honoured now raises `DeviceUnavailable`, the CLI turns that into
a `DeviceError` JSON document and the user (plus the log) learns why.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Dict, Literal, Optional, Tuple

DeviceType = Literal["cpu", "mps", "cuda"]

# Automatic preference order per OS: Apple Silicon has MPS and no CUDA, the
# desktop platforms have CUDA and no MPS.
ACCELERATOR_ORDER_MACOS: Tuple[str, ...] = ("mps", "cuda", "cpu")
ACCELERATOR_ORDER_OTHER: Tuple[str, ...] = ("cuda", "mps", "cpu")

_TORCH = None
_TORCH_ERROR: Optional[str] = None


class DeviceUnavailable(Exception):
    """Raised when an explicitly requested device cannot be used here."""

    pass


def is_macos() -> bool:
    """True on macOS, where MPS is a real accelerator for BeatNet."""
    return sys.platform == "darwin"


def _import_torch():
    """
    Import PyTorch once and return ``(module, error_message)``.

    WHY: On Windows a missing Visual C++ Redistributable or a missing CUDA
         runtime DLL makes `import torch` raise `OSError` instead of
         `ImportError`; catching only `ImportError` let those machines die with
         a traceback instead of a JSON error document.
    """
    global _TORCH, _TORCH_ERROR
    if _TORCH is not None or _TORCH_ERROR is not None:
        return _TORCH, _TORCH_ERROR

    try:
        import torch  # type: ignore

        _TORCH = torch
    except ImportError as exc:
        _TORCH_ERROR = f"PyTorch is not installed ({exc})"
    except OSError as exc:
        _TORCH_ERROR = (
            f"PyTorch failed to load ({exc}). On Windows this usually means the "
            "Visual C++ Redistributable or the CUDA runtime DLLs are missing."
        )
    except Exception as exc:  # pragma: no cover - exotic torch import failures
        _TORCH_ERROR = f"PyTorch failed to load ({type(exc).__name__}: {exc})"
    return _TORCH, _TORCH_ERROR


def _mps_works(torch) -> bool:
    """
    True when a tensor can actually be allocated on MPS.

    WHY: `torch.backends.mps.is_available()` can report True while the Metal
         device is unusable (headless session, exhausted VRAM); probing with a
         real allocation catches what BeatNet would hit later anyway.
    """
    backends = getattr(torch, "backends", None)
    mps = getattr(backends, "mps", None) if backends is not None else None
    if mps is None:
        return False
    try:
        if not bool(mps.is_available()):
            return False
        torch.zeros(1, device="mps")
        return True
    except Exception:
        return False


def _cuda_works(torch) -> bool:
    """
    True when CUDA is available *and* device 0 can be queried.

    WHY: `torch.cuda.is_available()` raises (`KeyError`, `AssertionError`,
         driver errors) on Windows when the installed driver and the CUDA
         runtime bundled with the wheel disagree; any exception therefore means
         "no CUDA" here, never "crash the service".
    """
    try:
        if not bool(torch.cuda.is_available()):
            return False
        torch.cuda.get_device_name(0)
        return True
    except Exception:
        return False


def _nvidia_gpu_visible() -> bool:
    """
    True when an NVIDIA GPU exists regardless of what torch thinks.

    WHY: the common support ticket is "I have a GPU but beat detection runs on
         CPU". Only `nvidia-smi` can tell a CPU-only wheel on a GPU machine
         apart from a machine with no NVIDIA card at all.
    """
    nvidia_smi = shutil.which("nvidia-smi") or shutil.which("nvidia-smi.exe")
    if not nvidia_smi:
        return False
    try:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def probe_devices() -> Dict[str, Tuple[bool, str]]:
    """
    Report every candidate device as ``(available, reason)``.

    The reason strings are user-facing: they name the missing wheel, driver or
    platform instead of just saying "not available".
    """
    torch, torch_error = _import_torch()
    version = getattr(torch, "__version__", "unknown") if torch else "unknown"

    if torch is None:
        reason = torch_error or "PyTorch unavailable"
        return {
            "cpu": (True, "CPU (always available)"),
            "mps": (False, f"Apple MPS unavailable: {reason}"),
            "cuda": (False, f"NVIDIA CUDA unavailable: {reason}"),
        }

    cuda_build = getattr(getattr(torch, "version", None), "cuda", None)

    if _cuda_works(torch):
        try:
            device_name = torch.cuda.get_device_name(0)
        except Exception:  # pragma: no cover - raced device teardown
            device_name = "unknown NVIDIA GPU"
        cuda: Tuple[bool, str] = (
            True,
            f"NVIDIA CUDA ({device_name}, torch build {cuda_build})",
        )
    elif cuda_build is None:
        if _nvidia_gpu_visible():
            # Visible here: a bare "cuda not available" would hide the fact
            # that only the *wheel* is wrong, not the hardware.
            cuda = (
                False,
                f"NVIDIA GPU detected, but this is a CPU-only PyTorch build "
                f"({version}). Install the CUDA wheel - see 'CUDA Installation' "
                f"in docs/PACKAGING.md.",
            )
        else:
            cuda = (
                False,
                f"NVIDIA CUDA unavailable: CPU-only PyTorch build ({version}) "
                "and no NVIDIA GPU detected",
            )
    else:
        cuda = (
            False,
            f"NVIDIA CUDA unavailable: PyTorch was built with CUDA (cu{cuda_build}) "
            "but the driver rejected it - update/enable the NVIDIA driver and "
            "check `nvidia-smi`.",
        )

    if _mps_works(torch):
        mps: Tuple[bool, str] = (
            True,
            "Apple Metal Performance Shaders (Apple Silicon GPU)",
        )
    elif not is_macos():
        mps = (False, f"Apple MPS unavailable: not supported on {sys.platform}")
    else:
        mps = (False, "Apple MPS unavailable: PyTorch reports no usable Metal device")

    return {"cpu": (True, "CPU (always available)"), "mps": mps, "cuda": cuda}


def _preference_order() -> Tuple[str, ...]:
    """Accelerator preference for the current OS (accelerators only)."""
    return ACCELERATOR_ORDER_MACOS if is_macos() else ACCELERATOR_ORDER_OTHER


def get_best_device() -> DeviceType:
    """
    Detect the best available PyTorch device.

    Priority:
    - macOS: MPS (Apple Silicon) > CUDA > CPU
    - Windows/Linux: CUDA > MPS > CPU

    Returns:
        Device string: 'cuda', 'mps' or 'cpu'.
    """
    return describe_best_device()[0]


def describe_best_device() -> Tuple[DeviceType, str]:
    """Return ``(device, reason)`` for the automatic choice."""
    devices = probe_devices()
    for candidate in _preference_order():
        available, reason = devices[candidate]
        if available:
            return candidate, reason  # type: ignore[return-value]
    return "cpu", devices["cpu"][1]


def resolve_device_with_reason(requested: str) -> Tuple[DeviceType, str]:
    """
    Same as :func:`resolve_device` but also returns the probe reason.

    WHY: the CLI logs the chosen device; without the reason the log only says
         "cuda" and nobody can tell a real GPU apart from a fallback.
    """
    normalized = (requested or "auto").strip().lower()

    if normalized in ("", "auto"):
        return describe_best_device()

    if normalized == "cpu":
        return "cpu", "CPU (requested explicitly)"

    if normalized not in ("mps", "cuda"):
        raise DeviceUnavailable(
            f"Unknown device '{requested}'; expected auto, mps, cuda or cpu."
        )

    if normalized == "mps" and not is_macos():
        # WHY: asking for MPS on Windows/Linux used to be answered with a
        # silent CPU run; naming the platform makes the mistake obvious.
        raise DeviceUnavailable(
            f"MPS is only available on macOS (running on {sys.platform}); "
            "choose 'cuda', 'cpu' or 'auto'."
        )

    devices = probe_devices()
    available, reason = devices[normalized]
    if not available:
        raise DeviceUnavailable(f"Requested device '{normalized}' unusable: {reason}")
    return normalized, reason


def resolve_device(requested: str) -> DeviceType:
    """
    Resolve a requested device to an actually usable one.

    Args:
        requested: 'auto', 'mps', 'cuda' or 'cpu'

    Returns:
        Resolved device string.

    Raises:
        DeviceUnavailable: when the requested device cannot be used here; the
            message explains why (never a silent switch to CPU).

    Behavior:
        - 'auto': best available device for this OS.
        - 'cpu': always honoured - CPU inference is a legitimate choice.
        - 'mps': refused off macOS; otherwise honoured when functional.
        - 'cuda': honoured only when a CUDA device answers.
    """
    return resolve_device_with_reason(requested)[0]


def device_report() -> str:
    """One-line summary of the automatic choice, for the CLI log."""
    device, reason = describe_best_device()
    return f"auto -> {device}: {reason}"
