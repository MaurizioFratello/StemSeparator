#!/usr/bin/env python3
"""
BeatNet Beat-Service CLI

PURPOSE: Standalone beat detection service for StemSeparator
CONTEXT: Runs as subprocess, communicates via JSON on stdout

Usage:
    beatnet-service --input /path/to/audio.wav [options]

Options:
    --input PATH        Audio file to analyze (required)
    --output PATH|-     Output JSON to file or stdout (default: -)
    --max-duration SEC  Limit analysis to first N seconds
    --device DEVICE     Device: auto|mps|cuda|cpu (default: auto)
    --verbose           Enable verbose logging to stderr
"""
import sys
import json
import argparse
import time
from pathlib import Path
from typing import Optional

try:
    from device import resolve_device
except ImportError:
    from src.device import resolve_device


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="beatnet-service",
        description="BeatNet beat and downbeat detection service"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="Path to audio file"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="-",
        help="Output path or '-' for stdout (default: -)"
    )
    parser.add_argument(
        "--max-duration",
        type=float,
        default=None,
        help="Maximum duration to analyze in seconds"
    )
    parser.add_argument(
        "--device",
        type=str,
        choices=["auto", "mps", "cuda", "cpu"],
        default="auto",
        help="Compute device (default: auto)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    return parser.parse_args()


def log(message: str, verbose: bool = False) -> None:
    """Log message to stderr if verbose mode is enabled."""
    if verbose:
        print(f"[beatnet-service] {message}", file=sys.stderr)


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


def analyze_audio(
    audio_path: Path,
    device: str,
    max_duration: Optional[float],
    verbose: bool
) -> dict:
    """
    Run BeatNet analysis on audio file.

    Args:
        audio_path: Path to audio file
        device: Compute device ('mps', 'cuda', 'cpu')
        max_duration: Optional max duration in seconds
        verbose: Enable verbose logging

    Returns:
        Analysis result dict
    """
    import soundfile as sf
    import numpy as np

    start_time = time.time()
    log(f"Loading audio: {audio_path}", verbose)

    # Load audio
    audio_data, sample_rate = sf.read(str(audio_path), always_2d=False)

    # Convert to mono if stereo
    if audio_data.ndim > 1:
        audio_data = np.mean(audio_data, axis=1)

    audio_duration = len(audio_data) / sample_rate
    log(f"Audio duration: {audio_duration:.2f}s, SR: {sample_rate} Hz", verbose)

    # Trim if max_duration specified
    if max_duration and audio_duration > max_duration:
        max_samples = int(max_duration * sample_rate)
        audio_data = audio_data[:max_samples]
        log(f"Trimmed to {max_duration:.2f}s", verbose)

    # Initialize BeatNet
    log(f"Initializing BeatNet on {device}...", verbose)

    from BeatNet.BeatNet import BeatNet

    predictor = BeatNet(
        model=1,
        mode='offline',
        inference_model='DBN',
        plot=[],
        thread=False,
        device=device
    )

    log("Running beat detection...", verbose)

    # Process audio
    # BeatNet.process() expects file path, so we pass the original path
    # BeatNet handles resampling internally to 22050 Hz
    result = predictor.process(str(audio_path))

    if result is None or len(result) == 0:
        output_error("AnalysisError", "No beats detected in audio")

    # Parse BeatNet output: array of [time, is_downbeat]
    beat_times = result[:, 0]
    downbeat_flags = result[:, 1]

    # Build structured output
    beats = []
    downbeats = []
    current_bar = 0
    beat_in_bar = 0
    beats_per_bar = 4  # Assume 4/4 time signature

    for i, (t, is_downbeat) in enumerate(zip(beat_times, downbeat_flags)):
        if is_downbeat == 1:
            current_bar += 1
            beat_in_bar = 1
            downbeats.append({
                "time": float(t),
                "bar": current_bar
            })
        else:
            beat_in_bar += 1

        beats.append({
            "time": float(t),
            "index": i,
            "bar": current_bar if current_bar > 0 else 1,
            "beat_in_bar": beat_in_bar if beat_in_bar > 0 else 1
        })

    # Estimate tempo from beat intervals
    if len(beat_times) > 1:
        intervals = np.diff(beat_times)
        median_interval = np.median(intervals)
        tempo = 60.0 / median_interval

        # Confidence based on interval consistency
        interval_std = np.std(intervals)
        tempo_confidence = max(0.0, 1.0 - (interval_std / median_interval))
    else:
        tempo = 120.0
        tempo_confidence = 0.0

    analysis_duration = time.time() - start_time
    log(f"Analysis complete in {analysis_duration:.2f}s", verbose)

    return {
        "version": "1.0.0",
        "model": "BeatNet-1.1.3",
        "backend": device,
        "tempo": round(tempo, 2),
        "tempo_confidence": round(tempo_confidence, 2),
        "time_signature": "4/4",
        "beats": beats,
        "downbeats": downbeats,
        "analysis_duration": round(analysis_duration, 2),
        "audio_duration": round(audio_duration, 2),
        "warnings": []
    }


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Validate input file
    if not args.input.exists():
        output_error(
            "InputError",
            f"Audio file not found: {args.input}",
            {"path": str(args.input)}
        )

    # Resolve device
    device = resolve_device(args.device)
    log(f"Using device: {device} (requested: {args.device})", args.verbose)

    try:
        # Run analysis
        result = analyze_audio(
            audio_path=args.input,
            device=device,
            max_duration=args.max_duration,
            verbose=args.verbose
        )

        # Output result
        output_json = json.dumps(result, indent=2)

        if args.output == "-":
            print(output_json)
        else:
            output_path = Path(args.output)
            output_path.write_text(output_json)
            log(f"Result written to: {output_path}", args.verbose)

        sys.exit(0)

    except ImportError as e:
        output_error(
            "DependencyError",
            f"Missing dependency: {e}",
            {"exception": str(e)}
        )
    except Exception as e:
        output_error(
            "AnalysisError",
            f"Analysis failed: {e}",
            {"exception": str(e), "type": type(e).__name__}
        )


if __name__ == "__main__":
    main()

