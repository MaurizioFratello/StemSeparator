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
import librosa

from config import ENSEMBLE_CONFIGS, DEFAULT_ENSEMBLE_CONFIG, MODELS, TEMP_DIR
from core.separator import Separator, SeparationResult
from utils.logger import get_logger

logger = get_logger()

# CRITICAL: Universal sample rate for all models and processing
# WHY: Mel-RoFormer and BS-RoFormer require 44100 Hz (hardcoded in model architecture)
#      All models must output at this exact rate to prevent timing drift/desynchronization
TARGET_SAMPLE_RATE = 44100


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
        progress_callback: Optional[Callable[[str, int], None]] = None,
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

        # Staged path: dedicated vocal stage then residual stage
        if "vocal_models" in config and "residual_models" in config:
            return self._separate_staged(
                audio_file=audio_file,
                config=config,
                output_dir=output_dir,
                quality_preset=quality_preset,
                progress_callback=progress_callback,
            )

        models = config["models"]
        weights = config["weights"]
        fusion_strategy = config.get("fusion_strategy", "waveform")
        fusion_stems = set(config.get("fusion_stems", []))
        mix_audio = None
        mix_sample_rate = None

        if fusion_strategy == "mask_blend":
            try:
                mix_audio_arr, mix_sample_rate = sf.read(
                    str(audio_file), always_2d=True, dtype="float32"
                )
                mix_audio = mix_audio_arr.T  # (channels, samples)

                # CRITICAL: Resample mix to TARGET_SAMPLE_RATE if needed
                # WHY: All processing must happen at 44100 Hz to prevent timing drift
                if mix_sample_rate != TARGET_SAMPLE_RATE:
                    self.logger.info(
                        f"Resampling input mix from {mix_sample_rate} Hz to {TARGET_SAMPLE_RATE} Hz "
                        f"(required for ensemble processing)"
                    )
                    mix_audio = self._resample_audio_array(
                        mix_audio, mix_sample_rate, TARGET_SAMPLE_RATE
                    )
                    mix_sample_rate = TARGET_SAMPLE_RATE
            except Exception as e:
                self.logger.warning(
                    f"Could not load mixture for mask blending: {e}. Falling back to waveform averaging."
                )
                fusion_strategy = "waveform"
                fusion_stems = set()

        self.logger.info(
            f"Starting ensemble separation: {audio_file.name} | "
            f"Config: {config['name']} | "
            f"Models: {models} | "
            f"Expected gain: {config['quality_gain']}"
        )

        if progress_callback:
            progress_callback(
                f"Starting {config['name']} with {len(models)} models...", 0
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
                    progress_start,
                )

            # Separiere mit diesem Modell
            result = self.separator.separate(
                audio_file=audio_file,
                model_id=model_id,
                output_dir=self._get_temp_dir(output_dir, model_id, audio_file),
                quality_preset=quality_preset,
                progress_callback=None,  # We handle progress ourselves
            )

            model_time = time.time() - model_start

            if not result.success:
                self.logger.error(f"Model {model_id} failed: {result.error_message}")
                # Continue with other models
                continue

            self.logger.info(
                f"Model {model_id} completed in {model_time:.1f}s: "
                f"{len(result.stems)} stems"
            )
            results.append(result)

            if progress_callback:
                progress_callback(f"Model {i+1}/{len(models)} complete", progress_end)

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
        combined_stems, combined_sr = self._combine_stems_weighted(
            results,
            weights,
            models[: len(results)],  # Only models that succeeded
            ensemble_config,  # Pass config to determine expected stems
            fusion_strategy=fusion_strategy,
            fusion_stems=fusion_stems,
            mix_audio=mix_audio,
            mix_sample_rate=mix_sample_rate,
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
            # Unified naming: stem name at the end, no ensemble/model suffix
            # WHY: Consistent naming across ensemble and normal modes
            output_file = output_dir / f"{audio_file.stem}_({stem_name}).wav"

            # Transpose to (samples, channels) for soundfile
            audio_to_save = audio_data.T

            # CRITICAL: Always use TARGET_SAMPLE_RATE (44100 Hz)
            # WHY: Prevents timing drift from sample rate mismatches between models
            #      Beat grid is calculated at 44100 Hz and must stay consistent
            if combined_sr and combined_sr != TARGET_SAMPLE_RATE:
                self.logger.warning(
                    f"Combined SR {combined_sr} Hz differs from target {TARGET_SAMPLE_RATE} Hz. "
                    f"This indicates a bug in sample rate handling!"
                )

            sf.write(
                str(output_file), audio_to_save, TARGET_SAMPLE_RATE, subtype="PCM_16"
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
            error_message=None,
        )

    def _separate_staged(
        self,
        audio_file: Path,
        config: dict,
        output_dir: Optional[Path],
        quality_preset: Optional[str],
        progress_callback: Optional[Callable[[str, int], None]],
    ) -> SeparationResult:
        """
        Staged flow: fuse vocals first, subtract residual, then process residual for drums/bass/other.
        """
        start_time = time.time()
        vocal_models = config.get("vocal_models", [])
        residual_models = config.get("residual_models", [])

        try:
            mix_audio_arr, mix_sample_rate = sf.read(
                str(audio_file), always_2d=True, dtype="float32"
            )
            mix_audio = mix_audio_arr.T  # (channels, samples)

            # CRITICAL: Resample mix to TARGET_SAMPLE_RATE if needed
            # WHY: All processing must happen at 44100 Hz to prevent timing drift
            if mix_sample_rate != TARGET_SAMPLE_RATE:
                self.logger.info(
                    f"Resampling input mix from {mix_sample_rate} Hz to {TARGET_SAMPLE_RATE} Hz "
                    f"(required for ensemble processing)"
                )
                mix_audio = self._resample_audio_array(
                    mix_audio, mix_sample_rate, TARGET_SAMPLE_RATE
                )
                mix_sample_rate = TARGET_SAMPLE_RATE
        except Exception as e:
            error_msg = f"Failed to load mix for staged ensemble: {e}"
            self.logger.error(error_msg)
            return self._create_error_result(audio_file, output_dir, error_msg)

        # 1) Vocal stage
        vocal_results = []
        for i, model_id in enumerate(vocal_models):
            if progress_callback:
                progress_callback(
                    f"Vocal stage {i+1}/{len(vocal_models)}: {MODELS.get(model_id, {}).get('name', model_id)}",
                    5 + i * 5,
                )
            res = self.separator.separate(
                audio_file=audio_file,
                model_id=model_id,
                output_dir=self._get_temp_dir(output_dir, model_id, audio_file),
                quality_preset=quality_preset,
                progress_callback=None,
            )
            if res.success:
                vocal_results.append(res)
            else:
                self.logger.warning(
                    f"Vocal model {model_id} failed: {res.error_message}"
                )

        if not vocal_results:
            return self._create_error_result(
                audio_file, output_dir, "All vocal models failed"
            )

        vocal_weights = config.get(
            "vocal_weights", {"vocals": [1.0 / len(vocal_results)] * len(vocal_results)}
        )
        vocals_audio, vocals_sr = self._combine_single_stem(
            results=vocal_results,
            model_ids=vocal_models[: len(vocal_results)],
            stem_name="vocals",
            weights=vocal_weights.get(
                "vocals", [1.0 / len(vocal_results)] * len(vocal_results)
            ),
            fusion_strategy=config.get("fusion_strategy", "waveform"),
            mix_audio=mix_audio,
            fallback_sample_rate=mix_sample_rate,
        )

        # FIX: Resample vocals to mix_sr (not vice versa) to preserve original mix SR
        # WHY: Keeps mix SR constant throughout pipeline, prevents cumulative resampling artifacts
        if vocals_sr and mix_sample_rate and vocals_sr != mix_sample_rate:
            self.logger.info(
                f"Resampling vocals from {vocals_sr} Hz to mix SR {mix_sample_rate} Hz"
            )
            vocals_audio = self._resample_audio_array(
                vocals_audio, vocals_sr, mix_sample_rate
            )
            vocals_sr = mix_sample_rate
        vocals_audio = self._align_length(vocals_audio, mix_audio.shape[1])

        # residual
        residual = mix_audio - vocals_audio
        peak = np.max(np.abs(residual))
        if peak > 1.0:
            residual = residual * (0.98 / peak)

        residual_path = self.cache_dir / f"{audio_file.stem}_residual.wav"
        sf.write(str(residual_path), residual.T, mix_sample_rate)

        # 2) Residual stage
        residual_results = []
        for i, model_id in enumerate(residual_models):
            if progress_callback:
                progress_callback(
                    f"Residual stage {i+1}/{len(residual_models)}: {MODELS.get(model_id, {}).get('name', model_id)}",
                    30 + i * 5,
                )
            res = self.separator.separate(
                audio_file=residual_path,
                model_id=model_id,
                output_dir=self._get_temp_dir(
                    output_dir, f"res_{model_id}", audio_file
                ),
                quality_preset=quality_preset,
                progress_callback=None,
            )
            if res.success:
                residual_results.append(res)
            else:
                self.logger.warning(
                    f"Residual model {model_id} failed: {res.error_message}"
                )

        if not residual_results:
            return self._create_error_result(
                audio_file, output_dir, "Residual models failed"
            )

        residual_weights = config.get("residual_weights", {})
        fusion_strategy = config.get("fusion_strategy", "waveform")
        fusion_stems = set(config.get("fusion_stems", []))

        combined_residual, combined_residual_sr = self._combine_stems_weighted(
            residual_results,
            residual_weights,
            residual_models[: len(residual_results)],
            ensemble_config=config.get("name", "staged"),
            fusion_strategy=fusion_strategy,
            fusion_stems=fusion_stems,
            mix_audio=residual,
            mix_sample_rate=mix_sample_rate,
            allowed_stems={"drums", "bass", "other"},
        )

        # Final stems
        output_dir = output_dir or self.separator.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        final_stems = {}

        # save vocals (mix_sample_rate is now guaranteed to be TARGET_SAMPLE_RATE)
        vocals_path = output_dir / f"{audio_file.stem}_(vocals).wav"
        sf.write(str(vocals_path), vocals_audio.T, TARGET_SAMPLE_RATE, subtype="PCM_16")
        final_stems["vocals"] = vocals_path

        # CRITICAL: Validate residual sample rate
        if combined_residual_sr and combined_residual_sr != TARGET_SAMPLE_RATE:
            self.logger.warning(
                f"Residual SR {combined_residual_sr} Hz differs from target {TARGET_SAMPLE_RATE} Hz. "
                f"This indicates a bug in sample rate handling!"
            )

        for stem_name, audio_data in combined_residual.items():
            audio_data = self._align_length(audio_data, mix_audio.shape[1])
            stem_path = output_dir / f"{audio_file.stem}_({stem_name}).wav"
            sf.write(str(stem_path), audio_data.T, TARGET_SAMPLE_RATE, subtype="PCM_16")
            final_stems[stem_name] = stem_path

        total_time = time.time() - start_time
        if progress_callback:
            progress_callback("Staged ensemble complete", 100)

        return SeparationResult(
            success=True,
            input_file=audio_file,
            output_dir=output_dir,
            stems=final_stems,
            model_used=f"ensemble_staged",
            device_used=self.separator.device_manager.get_device(),
            duration_seconds=total_time,
            error_message=None,
        )

    def _combine_stems_weighted(
        self,
        results: List[SeparationResult],
        weights_config: Dict[str, List[float]],
        model_ids: List[str],
        ensemble_config: str = "balanced",
        fusion_strategy: str = "waveform",
        fusion_stems: Optional[set] = None,
        mix_audio: Optional[np.ndarray] = None,
        mix_sample_rate: Optional[int] = None,
        allowed_stems: Optional[set] = None,
    ) -> Tuple[Dict[str, np.ndarray], Optional[int]]:
        """
        Kombiniert Stems mit stem-spezifischen Gewichten

        WHY: Verschiedene Modelle sind für verschiedene Stems besser
             (z.B. Mel-RoFormer für Vocals, Demucs für Drums)

        Args:
            results: Liste von SeparationResults
            weights_config: Stem-spezifische Gewichte
            model_ids: IDs der verwendeten Modelle
            fusion_strategy: 'waveform' (default) oder 'mask_blend'
            fusion_stems: Optional set of stems to apply mask blending on
            mix_audio: Optional mixture audio for mask blending (channels, samples)
            mix_sample_rate: Sample rate of mixture audio

        Returns:
            Dict mit combined stems: {stem_name: audio_data (channels, samples)}
        """
        combined = {}
        target_sample_rate: Optional[int] = None

        # Determine expected output stems based on ensemble config and model capabilities
        # WHY: We should output all stems that have weights defined and are available
        # from at least one model, not just collect arbitrary stems from files
        from config import ENSEMBLE_CONFIGS, MODELS

        # Get expected stems from weights_config (these are the stems we want to output)
        expected_stems = set(weights_config.keys())

        # Also collect stems that are actually produced by models (fallback)
        all_stem_names_from_files = set()
        for result in results:
            for stem_file in result.stems.values():
                stem_name = self._extract_stem_name(stem_file)
                all_stem_names_from_files.add(stem_name)

        # For Quality-Ensemble and similar configs, prioritize stems from 4-stem models
        # This ensures we output the full set (vocals, drums, bass, other) even if
        # 2-stem models only produce vocals and instrumental
        config_info = ENSEMBLE_CONFIGS.get(ensemble_config, {})
        config_models = config_info.get("models", [])

        # Get stem names from model configs (most comprehensive set)
        model_based_stems = set()
        for model_id in config_models:
            if model_id in MODELS:
                model_stems = MODELS[model_id].get("stem_names", [])
                # Normalize to lowercase
                model_based_stems.update([s.lower() for s in model_stems])

        # Combine: Use expected stems from weights, but also include any stems
        # that models actually produce (except instrumental which is handled separately)
        all_stem_names = expected_stems.copy()
        all_stem_names.update(
            [s for s in all_stem_names_from_files if s != "instrumental"]
        )

        # For ensembles with 4-stem models, include the 4-stem set
        # WHY: Even if 2-stem models only provide vocals, the 4-stem models
        # (bs-roformer, demucs_4s) provide drums/bass/other
        if any(
            model_id in ["bs-roformer", "demucs_4s", "demucs_6s"]
            for model_id in config_models
        ):
            four_stem_set = {"vocals", "drums", "bass", "other"}
            all_stem_names.update(four_stem_set)

        # Remove instrumental from final output
        # WHY: Instrumental is only relevant for 2-stem models (vocals/instrumental split)
        # We don't want to output it separately when we have individual instrument stems
        if "instrumental" in all_stem_names and len(all_stem_names) > 2:
            all_stem_names.remove("instrumental")

        if allowed_stems:
            all_stem_names = {s for s in all_stem_names if s in allowed_stems}

        self.logger.info(
            f"Target stems for ensemble output: {sorted(all_stem_names)} "
            f"(from config weights: {sorted(expected_stems)}, "
            f"from files: {sorted(all_stem_names_from_files)}, "
            f"from model configs: {sorted(model_based_stems)})"
        )

        # Für jeden Stem: gewichteter Durchschnitt
        for stem_name in all_stem_names:
            # Get weights for this stem (with fallback)
            stem_weights = weights_config.get(
                stem_name, [1.0 / len(results)] * len(results)  # Equal if not specified
            )

            # Nur so viele Gewichte wie wir Results haben
            stem_weights = stem_weights[: len(results)]

            self.logger.debug(
                f"Processing {stem_name}: initial weights={stem_weights} "
                f"(models: {model_ids})"
            )

            # Sammle Audio von allen Modellen für diesen Stem
            # WICHTIG: Sammle erst die verfügbaren Stems, dann normalisiere Gewichte
            stem_audios = []
            sample_rates = []
            available_weights = []  # Track which weights are actually used

            for i, result in enumerate(results):
                stem_file = self._find_stem_file(result, stem_name)

                if stem_file and stem_file.exists():
                    try:
                        audio, sr = sf.read(
                            str(stem_file), always_2d=True, dtype="float32"
                        )
                        audio = audio.T.astype(np.float32)  # (channels, samples)
                        stem_audios.append((audio, stem_weights[i], model_ids[i], sr))
                        sample_rates.append(sr)
                        available_weights.append(stem_weights[i])
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to load {stem_name} from {model_ids[i]}: {e}"
                        )
                else:
                    # Model doesn't have this specific stem - skip it
                    # WHY: Only use models that actually output pure stems for each type
                    # - 2-stem models (mel-roformer) only contribute to vocals
                    # - 4-stem models (bs-roformer, demucs) contribute to all stems
                    # DO NOT use "instrumental" for drums/bass/other because it's a MIX
                    # of all instruments, not a pure stem!
                    self.logger.info(
                        f"Stem '{stem_name}' not available from {model_ids[i]} "
                        f"(2-stem model only has vocals/instrumental) - skipping for this stem"
                    )

            if not stem_audios:
                self.logger.warning(f"No audio found for stem: {stem_name}")
                continue

            # Re-normalisiere Gewichte basierend auf tatsächlich verfügbaren Stems
            # Dies behebt das Problem, dass fehlende Stems (z.B. Mel-RoFormer ohne Drums)
            # die Gesamtlautstärke reduzieren würden
            total_available_weight = sum(available_weights)
            if total_available_weight > 0:
                normalized_weights = [
                    w / total_available_weight for w in available_weights
                ]
            else:
                normalized_weights = [1.0 / len(stem_audios)] * len(stem_audios)

            self.logger.info(
                f"Combining {stem_name} from {len(stem_audios)}/{len(results)} models: "
                f"normalized weights={[f'{w:.3f}' for w in normalized_weights]} "
                f"(models: {[model_id for _, _, model_id, _ in stem_audios]})"
            )

            # Update stem_audios with normalized weights
            stem_audios = [
                (audio, normalized_weights[i], model_id, sr)
                for i, (audio, _, model_id, sr) in enumerate(stem_audios)
            ]

            # CRITICAL: Always use TARGET_SAMPLE_RATE (44100 Hz)
            # WHY: Prevents cumulative resampling errors and timing drift
            #      Using first model's sample rate was causing progressive desync
            target_sr = TARGET_SAMPLE_RATE
            target_sample_rate = target_sr
            needs_resample = any(sr != target_sr for sr in sample_rates)

            # Validate mix_sample_rate if provided
            if mix_sample_rate and mix_sample_rate != TARGET_SAMPLE_RATE:
                self.logger.warning(
                    f"mix_sample_rate {mix_sample_rate} Hz differs from TARGET_SAMPLE_RATE {TARGET_SAMPLE_RATE} Hz. "
                    f"This should have been resampled earlier!"
                )

            if needs_resample:
                sr_info = ", ".join(
                    [f"{model_ids[i]}:{sr}Hz" for i, sr in enumerate(sample_rates)]
                )
                self.logger.warning(
                    f"Resampling {stem_name} stems to {target_sr} Hz (detected: {sr_info})"
                )

                resampled_audios = []
                for audio, weight, model_id, sr in stem_audios:
                    if target_sr is not None and sr != target_sr:
                        # FIX: Use librosa.resample instead of scipy.signal.resample
                        # WHY: librosa preserves audio quality better (phase-preserving, anti-aliasing)
                        # scipy.signal.resample is FFT-based and can cause timing/phase artifacts
                        resampled = self._resample_audio_array(audio, sr, target_sr)
                        resampled_audios.append((resampled, weight, model_id))
                    else:
                        resampled_audios.append((audio, weight, model_id))

                stem_audios = [
                    (audio, weight, model_id)
                    for audio, weight, model_id in resampled_audios
                ]
            else:
                stem_audios = [
                    (audio, weight, model_id)
                    for audio, weight, model_id, sr in stem_audios
                ]

            # Stelle sicher alle haben gleiche Länge (pad if necessary)
            max_length = max(audio.shape[1] for audio, _, _ in stem_audios)
            min_length = min(audio.shape[1] for audio, _, _ in stem_audios)
            length_diff = max_length - min_length

            # Warn about significant length differences
            if length_diff > 0:
                length_diff_ms = (length_diff / sample_rates[0]) * 1000
                if length_diff > sample_rates[0] * 0.1:  # More than 100ms difference
                    self.logger.warning(
                        f"Significant length difference for {stem_name}: "
                        f"{length_diff} samples ({length_diff_ms:.1f}ms). "
                        f"This could indicate different model processing or border effects."
                    )
                else:
                    self.logger.debug(
                        f"Minor length difference for {stem_name}: "
                        f"{length_diff} samples ({length_diff_ms:.1f}ms) - padding applied"
                    )

            padded_audios = []
            padded_weights = []

            for audio, weight, model_id in stem_audios:
                if audio.shape[1] < max_length:
                    padding = max_length - audio.shape[1]
                    audio = np.pad(audio, ((0, 0), (0, padding)), mode="constant")
                    self.logger.debug(
                        f"Padded {stem_name} from {model_id} with {padding} samples"
                    )
                elif audio.shape[1] > max_length:
                    audio = audio[:, :max_length]
                padded_audios.append(audio)
                padded_weights.append(weight)

            use_mask_blend = (
                fusion_strategy == "mask_blend"
                and mix_audio is not None
                and (not fusion_stems or stem_name in fusion_stems)
            )

            combined_audio = None
            if use_mask_blend:
                try:
                    combined_audio = self._mask_blend_stem(
                        mix_audio=mix_audio,
                        stem_audios=padded_audios,
                        stem_weights=padded_weights,
                        sample_rate=mix_sample_rate
                        or (sample_rates[0] if sample_rates else None),
                        target_length=max_length,
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Mask blend failed for {stem_name}, falling back to waveform average: {e}"
                    )
                    combined_audio = None

            if combined_audio is None:
                combined_audio = np.zeros((2, max_length), dtype=np.float32)

                for audio, weight in zip(padded_audios, padded_weights):
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

        return combined, target_sample_rate

    def _mask_blend_stem(
        self,
        mix_audio: np.ndarray,
        stem_audios: List[np.ndarray],
        stem_weights: List[float],
        sample_rate: Optional[int],
        target_length: Optional[int] = None,
        n_fft: int = 2048,
        hop_length: int = 512,
    ) -> np.ndarray:
        """
        Blend stems via soft masks on the mixture STFT.

        WHY: Keeps mixture phase and reduces interference vs. straight waveform averaging.
        """
        if sample_rate is None:
            sample_rate = 44100

        target_length = target_length or mix_audio.shape[1]
        mix = mix_audio

        if mix.shape[1] < target_length:
            mix = np.pad(
                mix, ((0, 0), (0, target_length - mix.shape[1])), mode="constant"
            )
        elif mix.shape[1] > target_length:
            mix = mix[:, :target_length]

        combined = np.zeros((mix.shape[0], target_length), dtype=np.float32)
        # FIX: Increased epsilon for more stable masks in quiet passages
        # WHY: 1e-6 can cause unstable masks when mix has very quiet frequencies
        eps = 1e-5

        for ch in range(mix.shape[0]):
            mix_spec = librosa.stft(mix[ch], n_fft=n_fft, hop_length=hop_length)
            weighted_mask = np.zeros_like(mix_spec, dtype=np.float32)

            for audio, weight in zip(stem_audios, stem_weights):
                stem_channel = audio[ch] if ch < audio.shape[0] else audio[-1]

                if stem_channel.shape[0] < target_length:
                    stem_channel = np.pad(
                        stem_channel, (0, target_length - stem_channel.shape[0])
                    )
                elif stem_channel.shape[0] > target_length:
                    stem_channel = stem_channel[:target_length]

                stem_spec = librosa.stft(
                    stem_channel, n_fft=n_fft, hop_length=hop_length
                )
                mask = np.abs(stem_spec) / (np.abs(mix_spec) + eps)
                weighted_mask += weight * np.clip(mask, 0.0, 1.2)

            # FIX: Increased final clipping threshold from 1.0 to 1.5
            # WHY: Allows mask to boost signal when mix is too quiet (e.g., after vocal subtraction)
            # The waveform soft-clipping below will handle any peaks > 1.0
            blended_spec = np.clip(weighted_mask, 0.0, 1.5) * mix_spec
            recon = librosa.istft(
                blended_spec, hop_length=hop_length, length=target_length
            )
            combined[ch, : recon.shape[0]] = np.nan_to_num(recon, nan=0.0)

        # Soft clipping if mask boosted signal too much
        peak = np.max(np.abs(combined))
        if peak > 1.0:
            combined = combined * (0.95 / peak)
            self.logger.debug(
                f"Mask blend boosted signal to {peak:.2f}, applied soft clipping"
            )

        return combined.astype(np.float32)

    def _combine_single_stem(
        self,
        results: List[SeparationResult],
        model_ids: List[str],
        stem_name: str,
        weights: List[float],
        fusion_strategy: str,
        mix_audio: np.ndarray,
        fallback_sample_rate: int,
    ) -> Tuple[np.ndarray, int]:
        """Combine only one stem (e.g., vocals) across results; returns (audio, sample_rate)."""
        audios = []
        used_weights = []
        stem_sample_rate = None

        for i, res in enumerate(results):
            stem_file = self._find_stem_file(res, stem_name)
            if stem_file and stem_file.exists():
                audio, sr = sf.read(str(stem_file), always_2d=True, dtype="float32")
                stem_sample_rate = stem_sample_rate or sr
                audio = audio.T  # (channels, samples)
                audios.append(audio)
                used_weights.append(weights[i] if i < len(weights) else 1.0)

        if not audios:
            raise RuntimeError(f"No audio found for stem {stem_name}")

        total = sum(used_weights)
        if total <= 0:
            used_weights = [1.0 / len(audios)] * len(audios)
        else:
            used_weights = [w / total for w in used_weights]

        max_len = max(a.shape[1] for a in audios)
        padded = []
        for a in audios:
            if a.shape[1] < max_len:
                a = np.pad(a, ((0, 0), (0, max_len - a.shape[1])), mode="constant")
            elif a.shape[1] > max_len:
                a = a[:, :max_len]
            padded.append(a)

        target_sr = stem_sample_rate or fallback_sample_rate
        use_mask_blend = fusion_strategy == "mask_blend" and mix_audio is not None

        def _waveform_fuse() -> np.ndarray:
            fused = np.zeros((2, max_len), dtype=np.float32)
            for a, w in zip(padded, used_weights):
                fused += a * w
            peak = np.max(np.abs(fused))
            if peak > 1.0:
                fused = fused * (0.98 / peak)
            return fused

        if use_mask_blend:
            try:
                mix_for_blend = mix_audio
                if (
                    target_sr
                    and fallback_sample_rate
                    and target_sr != fallback_sample_rate
                ):
                    mix_for_blend = self._resample_audio_array(
                        mix_audio, fallback_sample_rate, target_sr
                    )
                combined = self._mask_blend_stem(
                    mix_audio=mix_for_blend,
                    stem_audios=padded,
                    stem_weights=used_weights,
                    sample_rate=target_sr,
                    target_length=max_len,
                )
                # Guard: if mask blend produces very low energy vs sources, fallback to waveform
                if stem_name == "vocals":
                    rms_combined = float(np.sqrt(np.mean(combined**2)) + 1e-8)
                    rms_sources = [float(np.sqrt(np.mean(a**2)) + 1e-8) for a in padded]
                    median_src_rms = float(np.median(rms_sources))
                    if median_src_rms > 0 and rms_combined < 0.5 * median_src_rms:
                        self.logger.warning(
                            f"Mask blend for vocals too quiet (rms {rms_combined:.5f} vs median {median_src_rms:.5f}), "
                            "falling back to waveform fusion"
                        )
                        combined = _waveform_fuse()
                return combined, target_sr
            except Exception as e:
                self.logger.warning(
                    f"Mask blend for {stem_name} failed, fallback to waveform: {e}"
                )

        return _waveform_fuse(), target_sr

    def _align_length(self, audio: np.ndarray, target_len: int) -> np.ndarray:
        """Pad or trim stereo audio (2, N) to target length."""
        if audio.shape[1] == target_len:
            return audio
        if audio.shape[1] < target_len:
            pad = target_len - audio.shape[1]
            return np.pad(audio, ((0, 0), (0, pad)), mode="constant")
        return audio[:, :target_len]

    def _resample_audio_array(
        self, audio: np.ndarray, sr_in: int, sr_out: int
    ) -> np.ndarray:
        """Resample multi-channel audio array (channels, samples) to new sample rate."""
        if sr_in == sr_out:
            return audio
        try:
            resampled_channels = []
            for ch in range(audio.shape[0]):
                resampled_channels.append(
                    librosa.resample(audio[ch], orig_sr=sr_in, target_sr=sr_out)
                )
            # Ensure equal length across channels
            max_len = max(len(ch_data) for ch_data in resampled_channels)
            aligned = []
            for ch_data in resampled_channels:
                if len(ch_data) < max_len:
                    ch_data = np.pad(
                        ch_data, (0, max_len - len(ch_data)), mode="constant"
                    )
                elif len(ch_data) > max_len:
                    ch_data = ch_data[:max_len]
                aligned.append(ch_data)
            return np.stack(aligned, axis=0).astype(np.float32)
        except Exception as e:
            self.logger.warning(
                f"Resample failed ({sr_in}->{sr_out}), keeping original: {e}"
            )
            return audio

    def _extract_stem_name(self, file_path: Path) -> str:
        """
        Extrahiert Stem-Name aus Dateinamen

        WHY: Uses findall with known stem detection because input files might
        contain parentheses in the filename (e.g., "Song(2025)_(Vocals).wav")
        """
        name = file_path.stem

        # Known stem names for matching
        stem_keywords = [
            "vocals",
            "vocal",
            "drums",
            "drum",
            "bass",
            "other",
            "piano",
            "guitar",
            "instrumental",
            "instrum",
            "no_vocals",
            "no_other",
        ]

        # Find all parentheses content
        import re

        matches = re.findall(r"\(([^)]+)\)", name)

        if matches:
            # Try to find a known stem name in the matches (prefer last occurrence)
            for match in reversed(matches):
                match_lower = match.lower()
                for keyword in stem_keywords:
                    if keyword in match_lower or match_lower in keyword:
                        # Standardize names
                        if keyword in ["vocal", "vocals"]:
                            return "vocals"
                        elif keyword in ["drum", "drums"]:
                            return "drums"
                        elif keyword in ["instrum", "instrumental"]:
                            return "instrumental"
                        else:
                            return keyword

            # If no known stem found, return the last match
            return matches[-1].lower()

        # Fallback: look for known stem names anywhere in filename
        name_lower = name.lower()
        for keyword in stem_keywords:
            if keyword in name_lower:
                # Standardize names
                if keyword in ["vocal", "vocals"]:
                    return "vocals"
                elif keyword in ["drum", "drums"]:
                    return "drums"
                elif keyword in ["instrum", "instrumental"]:
                    return "instrumental"
                else:
                    return keyword

        return name.lower()

    def _find_stem_file(
        self, result: SeparationResult, stem_name: str
    ) -> Optional[Path]:
        """Findet Stem-Datei, auch mit alternativen Namen"""
        # Direkt nach stem_name in den Dateinamen suchen
        for file_path in result.stems.values():
            extracted_name = self._extract_stem_name(file_path)
            if extracted_name == stem_name:
                return file_path

        # Alternative Namen probieren
        alternatives = {
            "vocals": ["vocal", "voice", "singing"],
            "instrumental": ["instrum", "inst", "accompaniment", "music"],
            "drums": ["drum", "percussion", "percussive"],
            "bass": ["low", "bassline", "sub"],
            "other": ["others", "rest", "residual", "remainder"],
        }

        if stem_name in alternatives:
            for alt_name in alternatives[stem_name]:
                for file_path in result.stems.values():
                    extracted = self._extract_stem_name(file_path)
                    if alt_name in extracted or extracted in alt_name:
                        return file_path

        return None

    def _get_temp_dir(
        self, output_dir: Optional[Path], model_id: str, audio_file: Path
    ) -> Path:
        """Erstellt temporäres Verzeichnis für Model-Output"""
        if output_dir:
            temp_dir = output_dir / f"temp_{model_id}_{audio_file.stem}"
        else:
            temp_dir = self.cache_dir / f"{audio_file.stem}_{model_id}"

        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

    def _create_error_result(
        self, audio_file: Path, output_dir: Optional[Path], error_message: str
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
            error_message=error_message,
        )


# Global instance
_ensemble_separator: Optional[EnsembleSeparator] = None


def get_ensemble_separator() -> EnsembleSeparator:
    """Get global ensemble separator instance"""
    global _ensemble_separator
    if _ensemble_separator is None:
        _ensemble_separator = EnsembleSeparator()
    return _ensemble_separator
