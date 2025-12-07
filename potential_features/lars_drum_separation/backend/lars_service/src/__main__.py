#!/usr/bin/env python3
"""
LARS Service CLI

PURPOSE: Standalone drum separation service for StemSeparator
CONTEXT: Runs as subprocess, communicates via JSON on stdout

Usage:
    lars-service separate --input /path/to/drums.wav --output-dir /path/to/output [options]

Commands:
    separate    Separate drum stems

Options:
    --input PATH           Input audio file (required)
    --output-dir PATH      Output directory for stems (required)
    --stems LIST           Comma-separated list of stems: kick,snare,toms,hihat,cymbals (default: all)
    --device DEVICE        Device: auto|mps|cuda|cpu (default: auto)
    --wiener-filter        Enable Wiener filtering for better quality (default: False)
    --format FORMAT        Output format: wav|flac|mp3 (default: wav)
    --sample-rate RATE     Output sample rate in Hz (default: 44100)
    --verbose              Enable verbose logging to stderr
"""
import sys
import json
import argparse
import time
import multiprocessing
from pathlib import Path
from typing import Optional, List

# CRITICAL: PyInstaller + multiprocessing support
# This prevents "invalid choice: 'from multiprocessing.resource_tracker...'" errors
multiprocessing.freeze_support()

# Set multiprocessing start method (required for PyInstaller on macOS)
if __name__ == "__main__":
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        pass  # Already set

try:
    from device import resolve_device
    # Try to use actual LarsNet processor first (BEST)
    try:
        from lars_processor_larsnet import LarsProcessorLarsNet as LarsProcessor
        SEPARATION_BACKEND = "LarsNet (5 U-Nets)"
    except (ImportError, RuntimeError, Exception) as e:
        # Fall back to Demucs-based processor (GOOD)
        try:
            from lars_processor_demucs import LarsProcessorDemucs as LarsProcessor
            SEPARATION_BACKEND = "Demucs (workaround)"
        except (ImportError, Exception):
            # Fall back to placeholder if nothing else available (PLACEHOLDER)
            from lars_processor import LarsProcessor
            SEPARATION_BACKEND = "Placeholder (gain-based)"
except ImportError:
    from src.device import resolve_device
    try:
        from src.lars_processor_larsnet import LarsProcessorLarsNet as LarsProcessor
        SEPARATION_BACKEND = "LarsNet (5 U-Nets)"
    except (ImportError, RuntimeError, Exception):
        try:
            from src.lars_processor_demucs import LarsProcessorDemucs as LarsProcessor
            SEPARATION_BACKEND = "Demucs (workaround)"
        except (ImportError, Exception):
            from src.lars_processor import LarsProcessor
            SEPARATION_BACKEND = "Placeholder (gain-based)"


# Supported drum stems
SUPPORTED_STEMS = ["kick", "snare", "toms", "hihat", "cymbals"]
DEFAULT_STEMS = SUPPORTED_STEMS


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="lars-service",
        description="LARS drum separation service"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Separate command
    separate_parser = subparsers.add_parser("separate", help="Separate drum stems")
    separate_parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="Path to input audio file"
    )
    separate_parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        required=True,
        help="Output directory for separated stems"
    )
    separate_parser.add_argument(
        "--stems",
        type=str,
        default=",".join(DEFAULT_STEMS),
        help=f"Comma-separated list of stems to extract (default: all)"
    )
    separate_parser.add_argument(
        "--device",
        type=str,
        choices=["auto", "mps", "cuda", "cpu"],
        default="auto",
        help="Compute device (default: auto)"
    )
    separate_parser.add_argument(
        "--wiener-filter",
        action="store_true",
        help="Enable Wiener filtering for better quality"
    )
    separate_parser.add_argument(
        "--format",
        type=str,
        choices=["wav", "flac", "mp3"],
        default="wav",
        help="Output audio format (default: wav)"
    )
    separate_parser.add_argument(
        "--sample-rate",
        type=int,
        default=44100,
        help="Output sample rate in Hz (default: 44100)"
    )
    separate_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    return parser.parse_args()


def log(message: str, verbose: bool = False) -> None:
    """Log message to stderr if verbose mode is enabled."""
    if verbose:
        print(f"[lars-service] {message}", file=sys.stderr, flush=True)


def output_error(error_type: str, message: str, details: Optional[dict] = None) -> None:
    """Output error JSON to stdout and exit with code 1."""
    error = {
        "error": error_type,
        "message": message,
    }
    if details:
        error["details"] = details
    print(json.dumps(error, indent=2))
    sys.exit(1)


def output_result(result: dict) -> None:
    """Output result JSON to stdout."""
    print(json.dumps(result, indent=2))


def parse_stems_list(stems_str: str) -> List[str]:
    """
    Parse comma-separated stems list and validate.

    Args:
        stems_str: Comma-separated list of stem names

    Returns:
        List of valid stem names

    Raises:
        ValueError: If any stem name is invalid
    """
    stems = [s.strip().lower() for s in stems_str.split(",")]

    # Validate all stems
    invalid_stems = [s for s in stems if s not in SUPPORTED_STEMS]
    if invalid_stems:
        raise ValueError(
            f"Invalid stem names: {invalid_stems}. "
            f"Supported stems: {SUPPORTED_STEMS}"
        )

    return stems


def separate_drums(
    input_path: Path,
    output_dir: Path,
    stems: List[str],
    device: str,
    wiener_filter: bool,
    output_format: str,
    sample_rate: int,
    verbose: bool
) -> dict:
    """
    Separate drum stems from audio file.

    Args:
        input_path: Path to input audio file
        output_dir: Output directory for stems
        stems: List of stem names to extract
        device: Compute device ('mps', 'cuda', 'cpu')
        wiener_filter: Enable Wiener filtering
        output_format: Output format ('wav', 'flac', 'mp3')
        sample_rate: Output sample rate in Hz
        verbose: Enable verbose logging

    Returns:
        Separation result dict with paths to output files
    """
    start_time = time.time()
    log(f"Loading audio: {input_path}", verbose)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    log(f"Output directory: {output_dir}", verbose)

    # Initialize LARS processor
    log(f"Initializing LARS processor on {device} [{SEPARATION_BACKEND}]...", verbose)
    processor = LarsProcessor(device=device, verbose=verbose)

    # Run separation
    log(f"Separating stems: {', '.join(stems)}", verbose)
    log(f"Wiener filter: {'enabled' if wiener_filter else 'disabled'}", verbose)

    stem_paths = processor.separate(
        input_path=input_path,
        output_dir=output_dir,
        stems=stems,
        wiener_filter=wiener_filter,
        output_format=output_format,
        sample_rate=sample_rate
    )

    processing_time = time.time() - start_time
    log(f"Separation complete in {processing_time:.2f}s", verbose)

    # Build result
    result = {
        "version": "1.0.0",
        "model": "LARS",
        "backend": device,
        "stems": {
            stem: str(path) for stem, path in stem_paths.items()
        },
        "wiener_filter": wiener_filter,
        "output_format": output_format,
        "sample_rate": sample_rate,
        "processing_time": round(processing_time, 2),
        "warnings": []
    }

    return result


def main() -> None:
    """Main entry point."""
    args = parse_args()

    if args.command == "separate":
        # Validate input file
        if not args.input.exists():
            output_error(
                "InputError",
                f"Audio file not found: {args.input}",
                {"path": str(args.input)}
            )

        # Parse and validate stems list
        try:
            stems = parse_stems_list(args.stems)
        except ValueError as e:
            output_error(
                "ValidationError",
                str(e),
                {"stems": args.stems}
            )

        # Resolve device
        device = resolve_device(args.device)
        log(f"Using device: {device} (requested: {args.device})", args.verbose)

        try:
            # Run separation
            result = separate_drums(
                input_path=args.input,
                output_dir=args.output_dir,
                stems=stems,
                device=device,
                wiener_filter=args.wiener_filter,
                output_format=args.format,
                sample_rate=args.sample_rate,
                verbose=args.verbose
            )

            # Output result
            output_result(result)
            sys.exit(0)

        except ImportError as e:
            output_error(
                "DependencyError",
                f"Missing dependency: {e}",
                {"exception": str(e)}
            )
        except Exception as e:
            output_error(
                "SeparationError",
                f"Separation failed: {e}",
                {"exception": str(e), "type": type(e).__name__}
            )


if __name__ == "__main__":
    main()
