"""
Ensemble Separator - Kombiniert mehrere Modelle für höchste Qualität

PURPOSE: Nutzt die Stärken verschiedener Modelle (z.B. Mel-RoFormer für Vocals,
         Demucs für Drums) durch stem-spezifische Gewichtung
CONTEXT: Erreicht +0.5-1.0 dB SDR Verbesserung durch Model-Ensembles
"""
from pathlib import Path
from typing import Optional, Dict, Callable, List, Tuple
import time
import numpy as np
import soundfile as sf

from config import (
    ENSEMBLE_CONFIGS,
    DEFAULT_ENSEMBLE_CONFIG,
    MODELS,
    TEMP_DIR
)
from core.separator import Separator, SeparationResult
from utils.logger import get_logger

logger = get_logger()


class EnsembleSeparator:
    """
    Ensemble-basierte Stem Separation für höchste Qualität

    Kombiniert mehrere Modelle mit stem-spezifischen Gewichten:
    - Mel-RoFormer: Beste für Vocals (Gewicht 0.45)
    - BS-RoFormer: Ausgeglichen (Gewicht 0.35)
    - Demucs: Beste für Drums (Gewicht 0.50)

    Erreicht State-of-the-Art Qualität durch intelligentes Ensembling.
    """

    def __init__(self):
        self.separator = Separator()
        self.logger = logger
        self.cache_dir = TEMP_DIR / "ensemble_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info("EnsembleSeparator initialized")

    def separate_ensemble(
        self,
        audio_file: Path,
        ensemble_config: str = DEFAULT_ENSEMBLE_CONFIG,
        output_dir: Optional[Path] = None,
        quality_preset: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> SeparationResult:
        """
        Führt Ensemble-Separation durch

        Args:
            audio_file: Audio-Datei zum Separieren
            ensemble_config: 'balanced' (2 models), 'quality' (3 models), 'vocals_focus'
            output_dir: Output-Verzeichnis
            quality_preset: Quality preset für einzelne Modelle
            progress_callback: Callback(message, progress_percent)

        Returns:
            SeparationResult mit combined stems
        """
        start_time = time.time()

        # Validiere Ensemble-Config
        if ensemble_config not in ENSEMBLE_CONFIGS:
            error_msg = f"Unknown ensemble config: {ensemble_config}. Available: {list(ENSEMBLE_CONFIGS.keys())}"
            self.logger.error(error_msg)
            return self._create_error_result(audio_file, output_dir, error_msg)

        config = ENSEMBLE_CONFIGS[ensemble_config]
        models = config['models']
        weights = config['weights']

        self.logger.info(
            f"Starting ensemble separation: {audio_file.name} | "
            f"Config: {config['name']} | "
            f"Models: {models} | "
            f"Expected gain: {config['quality_gain']}"
        )

        if progress_callback:
            progress_callback(
                f"Starting {config['name']} with {len(models)} models...",
                0
            )

        # Validiere alle Modelle existieren
        for model_id in models:
            if model_id not in MODELS:
                error_msg = f"Model {model_id} not found in MODELS config"
                self.logger.error(error_msg)
                return self._create_error_result(audio_file, output_dir, error_msg)

        # Separiere mit jedem Modell
        results = []
        for i, model_id in enumerate(models):
            model_start = time.time()

            # Progress-Berechnung: 10-85% für Models, 85-100% für Combining
            progress_start = 10 + int((i / len(models)) * 75)
            progress_end = 10 + int(((i + 1) / len(models)) * 75)

            if progress_callback:
                progress_callback(
                    f"Model {i+1}/{len(models)}: {MODELS[model_id]['name']}",
                    progress_start
                )

            # Separiere mit diesem Modell
            result = self.separator.separate(
                audio_file=audio_file,
                model_id=model_id,
                output_dir=self._get_temp_dir(output_dir, model_id, audio_file),
                quality_preset=quality_preset,
                progress_callback=None  # We handle progress ourselves
            )

            model_time = time.time() - model_start

            if not result.success:
                self.logger.error(
                    f"Model {model_id} failed: {result.error_message}"
                )
                # Continue with other models
                continue

            self.logger.info(
                f"Model {model_id} completed in {model_time:.1f}s: "
                f"{len(result.stems)} stems"
            )
            results.append(result)

            if progress_callback:
                progress_callback(
                    f"Model {i+1}/{len(models)} complete",
                    progress_end
                )

        # Check if we have enough results
        if len(results) < len(models):
            self.logger.warning(
                f"Only {len(results)}/{len(models)} models succeeded. "
                f"Quality may be reduced."
            )

        if not results:
            error_msg = "All models failed"
            self.logger.error(error_msg)
            return self._create_error_result(audio_file, output_dir, error_msg)

        # Kombiniere Ergebnisse mit stem-spezifischen Gewichten
        if progress_callback:
            progress_callback("Combining stems with weighted averaging...", 87)

        combining_start = time.time()
        combined_stems = self._combine_stems_weighted(
            results,
            weights,
            models[:len(results)]  # Only models that succeeded
        )
        combining_time = time.time() - combining_start

        self.logger.info(
            f"Combined {len(results)} models in {combining_time:.1f}s -> "
            f"{len(combined_stems)} stems"
        )

        # Speichere kombinierte Stems
        if progress_callback:
            progress_callback("Saving ensemble results...", 95)

        output_dir = output_dir or self.separator.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        final_stems = {}
        for stem_name, audio_data in combined_stems.items():
            output_file = output_dir / f"{audio_file.stem}_{stem_name}_ensemble.wav"

            # Transpose to (samples, channels) for soundfile
            audio_to_save = audio_data.T

            sf.write(
                str(output_file),
                audio_to_save,
                results[0].stems.get('sample_rate', 44100),  # Get from first result
                subtype='PCM_16'
            )

            final_stems[stem_name] = output_file
            self.logger.debug(f"Saved {stem_name}: {output_file.name}")

        total_time = time.time() - start_time

        if progress_callback:
            progress_callback("Ensemble separation complete!", 100)

        self.logger.info(
            f"Ensemble separation completed in {total_time:.1f}s "
            f"({total_time / len(results):.1f}s per model)"
        )

        return SeparationResult(
            success=True,
            input_file=audio_file,
            output_dir=output_dir,
            stems=final_stems,
            model_used=f"ensemble_{ensemble_config}",
            device_used=self.separator.device_manager.get_device(),
            duration_seconds=total_time,
            error_message=None
        )

    def _combine_stems_weighted(
        self,
        results: List[SeparationResult],
        weights_config: Dict[str, List[float]],
        model_ids: List[str]
    ) -> Dict[str, np.ndarray]:
        """
        Kombiniert Stems mit stem-spezifischen Gewichten

        WHY: Verschiedene Modelle sind für verschiedene Stems besser
             (z.B. Mel-RoFormer für Vocals, Demucs für Drums)

        Args:
            results: Liste von SeparationResults
            weights_config: Stem-spezifische Gewichte
            model_ids: IDs der verwendeten Modelle

        Returns:
            Dict mit combined stems: {stem_name: audio_data (channels, samples)}
        """
        combined = {}

        # Finde alle Stem-Namen über alle Results
        all_stem_names = set()
        for result in results:
            # Extract stem names from filenames
            for stem_file in result.stems.values():
                stem_name = self._extract_stem_name(stem_file)
                all_stem_names.add(stem_name)

        self.logger.debug(f"Found stems: {all_stem_names}")

        # Für jeden Stem: gewichteter Durchschnitt
        for stem_name in all_stem_names:
            # Get weights for this stem (with fallback)
            stem_weights = weights_config.get(
                stem_name,
                [1.0 / len(results)] * len(results)  # Equal if not specified
            )

            # Nur so viele Gewichte wie wir Results haben
            stem_weights = stem_weights[:len(results)]

            # Normalisiere Gewichte
            total_weight = sum(stem_weights)
            if total_weight > 0:
                normalized_weights = [w / total_weight for w in stem_weights]
            else:
                normalized_weights = [1.0 / len(results)] * len(results)

            self.logger.debug(
                f"Combining {stem_name}: weights={normalized_weights} "
                f"(models: {model_ids})"
            )

            # Sammle Audio von allen Modellen für diesen Stem
            stem_audios = []
            for i, result in enumerate(results):
                stem_file = self._find_stem_file(result, stem_name)

                if stem_file and stem_file.exists():
                    try:
                        audio, sr = sf.read(str(stem_file), always_2d=True, dtype='float32')
                        audio = audio.T.astype(np.float32)  # (channels, samples)
                        stem_audios.append((audio, normalized_weights[i], model_ids[i]))
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to load {stem_name} from {model_ids[i]}: {e}"
                        )
                else:
                    self.logger.warning(
                        f"Stem {stem_name} not found in result from {model_ids[i]}"
                    )

            if not stem_audios:
                self.logger.warning(f"No audio found for stem: {stem_name}")
                continue

            # Stelle sicher alle haben gleiche Länge (pad if necessary)
            max_length = max(audio.shape[1] for audio, _, _ in stem_audios)
            padded_audios = []

            for audio, weight, model_id in stem_audios:
                if audio.shape[1] < max_length:
                    padding = max_length - audio.shape[1]
                    audio = np.pad(audio, ((0, 0), (0, padding)), mode='constant')
                    self.logger.debug(
                        f"Padded {stem_name} from {model_id} with {padding} samples"
                    )
                padded_audios.append((audio, weight))

            # Weighted Average
            combined_audio = np.zeros((2, max_length), dtype=np.float32)

            for audio, weight in padded_audios:
                combined_audio += audio * weight

            # Soft clipping für Sicherheit
            peak = np.max(np.abs(combined_audio))
            if peak > 1.0:
                combined_audio = combined_audio * (0.95 / peak)
                self.logger.debug(
                    f"Applied soft clipping to {stem_name} (peak was {peak:.2f})"
                )

            combined[stem_name] = combined_audio
            self.logger.debug(
                f"Combined {stem_name}: shape={combined_audio.shape}, "
                f"peak={np.max(np.abs(combined_audio)):.3f}"
            )

        return combined

    def _extract_stem_name(self, file_path: Path) -> str:
        """Extrahiert Stem-Name aus Dateinamen"""
        name = file_path.stem

        # Remove filename prefix (e.g., "song_(vocals)_model" -> "vocals")
        # Try to extract from parentheses first
        import re
        match = re.search(r'\(([^)]+)\)', name)
        if match:
            return match.group(1).lower()

        # Otherwise look for known stem names
        stem_keywords = ['vocals', 'vocal', 'drums', 'drum', 'bass', 'other',
                        'piano', 'guitar', 'instrumental', 'instrum']

        name_lower = name.lower()
        for keyword in stem_keywords:
            if keyword in name_lower:
                # Standardize names
                if keyword in ['vocal', 'vocals']:
                    return 'vocals'
                elif keyword in ['drum', 'drums']:
                    return 'drums'
                elif keyword in ['instrum', 'instrumental']:
                    return 'instrumental'
                else:
                    return keyword

        return name.lower()

    def _find_stem_file(self, result: SeparationResult, stem_name: str) -> Optional[Path]:
        """Findet Stem-Datei, auch mit alternativen Namen"""
        # Direkt nach stem_name in den Dateinamen suchen
        for file_path in result.stems.values():
            extracted_name = self._extract_stem_name(file_path)
            if extracted_name == stem_name:
                return file_path

        # Alternative Namen probieren
        alternatives = {
            'vocals': ['vocal', 'voice', 'singing'],
            'instrumental': ['instrum', 'inst', 'accompaniment', 'music'],
            'drums': ['drum', 'percussion', 'percussive'],
            'bass': ['low', 'bassline', 'sub'],
            'other': ['others', 'rest', 'residual', 'remainder']
        }

        if stem_name in alternatives:
            for alt_name in alternatives[stem_name]:
                for file_path in result.stems.values():
                    extracted = self._extract_stem_name(file_path)
                    if alt_name in extracted or extracted in alt_name:
                        return file_path

        return None

    def _get_temp_dir(self, output_dir: Optional[Path], model_id: str, audio_file: Path) -> Path:
        """Erstellt temporäres Verzeichnis für Model-Output"""
        if output_dir:
            temp_dir = output_dir / f"temp_{model_id}_{audio_file.stem}"
        else:
            temp_dir = self.cache_dir / f"{audio_file.stem}_{model_id}"

        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

    def _create_error_result(
        self,
        audio_file: Path,
        output_dir: Optional[Path],
        error_message: str
    ) -> SeparationResult:
        """Creates error result"""
        return SeparationResult(
            success=False,
            input_file=audio_file,
            output_dir=output_dir or self.separator.output_dir,
            stems={},
            model_used="ensemble",
            device_used="",
            duration_seconds=0,
            error_message=error_message
        )


# Global instance
_ensemble_separator: Optional[EnsembleSeparator] = None


def get_ensemble_separator() -> EnsembleSeparator:
    """Get global ensemble separator instance"""
    global _ensemble_separator
    if _ensemble_separator is None:
        _ensemble_separator = EnsembleSeparator()
    return _ensemble_separator
