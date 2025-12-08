"""
Device Detection for BeatNet Beat-Service

PURPOSE: Detect best available compute device for PyTorch inference
CONTEXT: Prioritizes MPS (Apple Silicon) > CUDA > CPU
"""

from typing import Literal

DeviceType = Literal["cpu", "mps", "cuda"]


def get_best_device() -> DeviceType:
    """
    Detect best available PyTorch device.

    Priority:
    1. MPS (Apple Silicon Metal Performance Shaders)
    2. CUDA (NVIDIA GPU)
    3. CPU (fallback)

    Returns:
        Device string: 'mps', 'cuda', or 'cpu'
    """
    try:
        import torch

        # Check MPS (Apple Silicon)
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            # Verify MPS is actually functional
            try:
                _ = torch.zeros(1, device="mps")
                return "mps"
            except Exception:
                pass  # MPS available but not functional

        # Check CUDA (NVIDIA)
        if torch.cuda.is_available():
            return "cuda"

        return "cpu"

    except ImportError:
        return "cpu"


def resolve_device(requested: str) -> DeviceType:
    """
    Resolve requested device to actual available device.

    Args:
        requested: 'auto', 'mps', 'cuda', or 'cpu'

    Returns:
        Resolved device string

    Behavior:
        - 'auto': returns best available device
        - specific device: returns that device if available, else 'cpu'
    """
    if requested == "auto":
        return get_best_device()

    if requested == "mps":
        try:
            import torch

            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    if requested == "cuda":
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"

    return "cpu"
