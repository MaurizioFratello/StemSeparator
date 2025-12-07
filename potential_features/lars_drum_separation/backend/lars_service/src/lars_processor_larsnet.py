#!/usr/bin/env python3
"""
LarsNet-based LARS Processor

PURPOSE: Real drum separation using the actual LarsNet model
ARCHITECTURE: 5 parallel U-Nets for drum component separation
REFERENCE: https://github.com/polimi-ispl/larsnet

LarsNet Details:
- 5 parallel U-Nets (Kick, Snare, Toms, Hi-Hat, Cymbals)
- Trained on StemGMD dataset (1,224 hours)
- Faster than real-time processing
- Optional α-Wiener filtering for cross-talk reduction
"""
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import soundfile as sf
import librosa

# CRITICAL: Disable multiprocessing for PyInstaller compatibility
# This prevents the "resource_tracker" errors when running in bundled binary
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'

# Add larsnet directory to Python path
LARSNET_DIR = Path(__file__).parent.parent / "larsnet"
if LARSNET_DIR.exists():
    sys.path.insert(0, str(LARSNET_DIR))


class LarsProcessorLarsNet:
    """
    LARS processor using actual LarsNet model.

    Wraps the LarsNet implementation from Politecnico di Milano.
    """

    SUPPORTED_STEMS = ["kick", "snare", "toms", "hihat", "cymbals"]

    def __init__(
        self,
        device: str = "cpu",
        verbose: bool = False
    ):
        """
        Initialize LarsNet processor.

        Args:
            device: PyTorch device ('cpu', 'cuda', 'mps')
            verbose: Enable verbose logging

        Raises:
            ImportError: If LarsNet is not available
            RuntimeError: If pretrained models are not found
        """
        self.device = device
        self.verbose = verbose
        self.model = None

        # Check if LarsNet is available
        try:
            from larsnet import LarsNet
            self.LarsNet = LarsNet
        except ImportError as e:
            raise ImportError(
                "LarsNet not found. Please clone the repository:\n"
                "  cd packaging/lars_service/\n"
                "  git clone https://github.com/polimi-ispl/larsnet.git"
            ) from e

        # Check if pretrained models exist
        self._check_pretrained_models()

        self._log("LarsNet processor initialized")

    def _check_pretrained_models(self) -> None:
        """
        Check if pretrained models are available.

        Raises:
            RuntimeError: If models directory doesn't exist or is empty
        """
        models_dir = LARSNET_DIR / "pretrained_larsnet_models"

        if not models_dir.exists():
            raise RuntimeError(
                "Pretrained models not found!\n\n"
                "Please download the models (562 MB):\n"
                "1. Download: https://drive.google.com/file/d/1bFwCkjjIbuDkMGkWkUPglZKoP31XTFYZ/view\n"
                "2. Extract the downloaded file\n"
                f"3. Place in: {models_dir}\n\n"
                "Expected structure:\n"
                "  pretrained_larsnet_models/\n"
                "    ├── kick/pretrained_kick_unet.pth\n"
                "    ├── snare/pretrained_snare_unet.pth\n"
                "    ├── toms/pretrained_toms_unet.pth\n"
                "    ├── hihat/pretrained_hihat_unet.pth\n"
                "    └── cymbals/pretrained_cymbals_unet.pth"
            )

        # Check if model files exist
        expected_models = [
            "kick/pretrained_kick_unet.pth",
            "snare/pretrained_snare_unet.pth",
            "toms/pretrained_toms_unet.pth",
            "hihat/pretrained_hihat_unet.pth",
            "cymbals/pretrained_cymbals_unet.pth",
        ]

        missing_models = []
        for model_path in expected_models:
            full_path = models_dir / model_path
            if not full_path.exists():
                missing_models.append(model_path)

        if missing_models:
            raise RuntimeError(
                f"Missing model files: {missing_models}\n\n"
                "Please download the pretrained models as described above."
            )

    def _log(self, message: str) -> None:
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(f"[LarsNet] {message}", file=sys.stderr, flush=True)

    def _load_model(self, wiener_filter: bool = False, wiener_exponent: float = 1.0) -> None:
        """
        Load LarsNet model with specified configuration.

        Args:
            wiener_filter: Enable Wiener filtering
            wiener_exponent: α-Wiener filter exponent (only used if wiener_filter=True)
        """
        if self.model is not None:
            # Model already loaded
            return

        config_path = LARSNET_DIR / "config.yaml"
        if not config_path.exists():
            raise RuntimeError(f"LarsNet config not found: {config_path}")

        self._log(f"Loading LarsNet models from {LARSNET_DIR}")
        self._log(f"Device: {self.device}")
        if wiener_filter:
            self._log(f"Wiener filtering enabled (α={wiener_exponent})")

        # Disable PyTorch multiprocessing for PyInstaller compatibility
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)

        # Change to larsnet directory so config paths resolve correctly
        original_cwd = os.getcwd()
        try:
            os.chdir(LARSNET_DIR)

            # Initialize LarsNet
            self.model = self.LarsNet(
                wiener_filter=wiener_filter,
                wiener_exponent=wiener_exponent if wiener_filter else 1.0,
                config=str(config_path),
                return_stft=False,
                device=self.device
            )

        finally:
            os.chdir(original_cwd)

        self._log("LarsNet models loaded successfully")

    def separate(
        self,
        input_path: Path,
        output_dir: Path,
        stems: Optional[List[str]] = None,
        wiener_filter: bool = False,
        output_format: str = "wav",
        sample_rate: int = 44100
    ) -> Dict[str, Path]:
        """
        Separate drum stems from audio file using LarsNet.

        Args:
            input_path: Path to input audio file
            output_dir: Output directory for separated stems
            stems: List of stems to extract (default: all)
            wiener_filter: Enable Wiener filtering for better quality
            output_format: Output format ('wav', 'flac', 'mp3')
            sample_rate: Target sample rate (LarsNet uses 44100 Hz internally)

        Returns:
            Dictionary mapping stem names to output file paths

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If invalid stem names are specified
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Default to all stems if not specified
        if stems is None:
            stems = self.SUPPORTED_STEMS.copy()

        # Validate stems
        invalid_stems = [s for s in stems if s not in self.SUPPORTED_STEMS]
        if invalid_stems:
            raise ValueError(
                f"Invalid stem names: {invalid_stems}. "
                f"Supported: {self.SUPPORTED_STEMS}"
            )

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Load model (with appropriate Wiener filter settings)
        wiener_exponent = 1.0  # Default α value
        self._load_model(wiener_filter=wiener_filter, wiener_exponent=wiener_exponent)

        self._log(f"Processing: {input_path.name}")
        self._log(f"Extracting stems: {', '.join(stems)}")

        # Run LarsNet separation
        # LarsNet's forward() method accepts file path and handles loading/resampling
        separated_stems = self.model(str(input_path))

        # LarsNet returns dict of {stem_name: torch.Tensor}
        # Tensors are shape [channels, samples] on the device
        self._log(f"Separation complete, saving {len(stems)} stems...")

        # Save requested stems
        stem_paths = {}
        for stem_name in stems:
            if stem_name not in separated_stems:
                self._log(f"Warning: {stem_name} not in LarsNet output, skipping")
                continue

            # Get waveform tensor and convert to numpy
            waveform_tensor = separated_stems[stem_name]  # [channels, samples]
            waveform = waveform_tensor.cpu().numpy()  # Move to CPU and convert

            # LarsNet outputs [channels, samples], need to transpose for soundfile
            if waveform.ndim == 2:
                waveform = waveform.T  # [samples, channels]

            # LarsNet uses 44100 Hz internally
            larsnet_sr = 44100

            # Resample if needed
            if sample_rate != larsnet_sr:
                self._log(f"Resampling {stem_name}: {larsnet_sr} Hz -> {sample_rate} Hz")
                # Transpose back for librosa: [channels, samples]
                waveform = waveform.T if waveform.ndim == 2 else waveform
                waveform = librosa.resample(
                    waveform,
                    orig_sr=larsnet_sr,
                    target_sr=sample_rate,
                    res_type='kaiser_best'
                )
                # Transpose back for soundfile: [samples, channels]
                waveform = waveform.T if waveform.ndim == 2 else waveform

            # Build output path
            stem_filename = f"{input_path.stem}_{stem_name}.{output_format}"
            output_path = output_dir / stem_filename

            # Save audio file
            sf.write(
                output_path,
                waveform,
                sample_rate,
                format=output_format.upper()
            )

            stem_paths[stem_name] = output_path
            self._log(f"  {stem_name}: {output_path.name}")

        self._log("All stems saved successfully")
        return stem_paths
