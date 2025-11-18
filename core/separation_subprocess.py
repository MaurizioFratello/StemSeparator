"""
Separation Subprocess Worker

PURPOSE: Run audio separation in isolated subprocess to prevent resource leaks
CONTEXT: audio-separator library has multiprocessing semaphore leaks that cause
         segfaults on repeated use. Running each separation in a subprocess
         ensures OS cleans up all resources when subprocess exits.
"""
import sys
import json
from pathlib import Path
from typing import Dict, Optional
import re


def run_separation_subprocess(
    audio_file: Path,
    model_id: str,
    output_dir: Path,
    model_filename: str,
    models_dir: Path,
    preset_params: dict,
    preset_attributes: dict,
    device: str = 'cpu'
) -> Dict[str, Path]:
    """
    Run separation in subprocess - guaranteed clean resource management

    Args:
        audio_file: Path to audio file
        model_id: Model identifier
        output_dir: Output directory
        model_filename: Model filename to load
        models_dir: Directory containing models
        preset_params: Quality preset parameters
        preset_attributes: Quality preset attributes
        device: Device to use ('cpu', 'mps', 'cuda')

    Returns:
        Dict mapping stem names to output file paths
    """
    # Import here to keep subprocess isolated
    from audio_separator.separator import Separator as AudioSeparator

    # Create separator instance
    separator = AudioSeparator(
        log_level=20,  # INFO
        model_file_dir=str(models_dir),
        output_dir=str(output_dir),
        **preset_params
    )

    # Set architecture-specific attributes
    for attr_name, attr_value in preset_attributes.items():
        setattr(separator, attr_name, attr_value)

    # Load model
    separator.load_model(model_filename=model_filename)

    # Run separation
    output_files = separator.separate(str(audio_file))

    # Parse output files
    stems = {}
    if isinstance(output_files, list):
        for file_path in output_files:
            file_path = Path(file_path)

            # Make absolute if needed
            if not file_path.is_absolute():
                file_path = output_dir / file_path

            # Extract stem name from filename
            # Format: filename_(stem).wav or filename_(stem)_modelname.wav
            match = re.search(r'\(([^)]+)\)', file_path.stem)
            if match:
                stem_name = match.group(1)
            else:
                stem_name = file_path.stem.split('_')[-1]

            stems[stem_name] = str(file_path)  # Convert to string for JSON serialization

    return stems


if __name__ == "__main__":
    # Read parameters from stdin as JSON
    params = json.loads(sys.stdin.read())

    # Convert string paths back to Path objects
    params['audio_file'] = Path(params['audio_file'])
    params['output_dir'] = Path(params['output_dir'])
    params['models_dir'] = Path(params['models_dir'])

    try:
        # Run separation
        stems = run_separation_subprocess(**params)

        # Write result to stdout as JSON
        result = {
            'success': True,
            'stems': stems,
            'error': None
        }
        print(json.dumps(result))
        sys.exit(0)

    except Exception as e:
        # Write error to stdout as JSON
        result = {
            'success': False,
            'stems': {},
            'error': str(e)
        }
        print(json.dumps(result))
        sys.exit(1)
