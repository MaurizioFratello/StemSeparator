"""
Model Manager für das Herunterladen und Verwalten von Separation-Modellen
"""

import os
from pathlib import Path
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass

from config import MODELS, DEFAULT_MODEL, MODELS_DIR
from utils.logger import get_logger
from utils.error_handler import retry_on_error

logger = get_logger()


@dataclass
class ModelInfo:
    """Informationen über ein Modell"""

    name: str
    stems: int
    size_mb: int
    description: str
    model_filename: str  # audio-separator model filename
    backend: str = "auto"  # e.g. mdx, demucs, roformer
    downloaded: bool = False
    path: Optional[Path] = None
    stem_names: Optional[List[str]] = (
        None  # List of stem names (e.g., ['Vocals', 'Instrumental'])
    )


class ModelManager:
    """Verwaltet Audio-Separation-Modelle"""

    def __init__(self):
        self.models_dir = MODELS_DIR
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.available_models: Dict[str, ModelInfo] = {}
        self._load_model_info()
        logger.info("ModelManager initialized")

    def _load_model_info(self):
        """Lädt Informationen über verfügbare Modelle"""
        for model_id, model_config in MODELS.items():
            model_info = ModelInfo(
                name=model_config["name"],
                stems=model_config["stems"],
                size_mb=model_config["size_mb"],
                description=model_config["description"],
                model_filename=model_config["model_filename"],
                backend=model_config.get("backend", "auto"),
                stem_names=model_config.get(
                    "stem_names"
                ),  # Optional: list of stem names
            )

            # Prüfe ob Modell bereits heruntergeladen ist
            if self._verify_model(model_info.model_filename):
                model_info.downloaded = True
                model_info.path = self.models_dir / model_info.model_filename
                logger.info(f"Model '{model_id}' found and verified")
            else:
                logger.info(f"Model '{model_id}' not downloaded")

            self.available_models[model_id] = model_info

    def _verify_model(self, model_filename: str) -> bool:
        """
        Verifiziert ob ein Modell gültig ist

        audio-separator speichert Modelle direkt im models_dir, nicht in Unterverzeichnissen.
        Für YAML-Modelle (Demucs) prüfen wir ob die YAML-Datei existiert und die referenzierten
        Gewichtsdateien vorhanden sind.
        """
        # Prüfe ob die Modelldatei im models_dir existiert
        model_path = self.models_dir / model_filename

        if not model_path.exists():
            return False

        # Für YAML-Dateien (Demucs-Modelle): Prüfe ob referenzierte .th-Dateien existieren
        if model_filename.endswith(".yaml"):
            try:
                import yaml

                with open(model_path, "r") as f:
                    config = yaml.safe_load(f)

                # Prüfe ob referenzierte Modell-IDs existieren
                if "models" in config:
                    for model_id in config["models"]:
                        # Suche nach .th-Dateien die mit der model_id beginnen
                        matching_files = list(self.models_dir.glob(f"{model_id}*.th"))
                        if not matching_files:
                            return False

                        # Prüfe ob die Datei groß genug ist (mindestens 10MB für Demucs)
                        for th_file in matching_files:
                            if th_file.stat().st_size < 10 * 1024 * 1024:
                                return False

                return True
            except Exception as e:
                logger.warning(f"Error verifying YAML model {model_filename}: {e}")
                return False

        # Für andere Modelltypen (.ckpt, .pth, etc.): Prüfe Dateigröße
        else:
            model_extensions = [".pth", ".pt", ".ckpt", ".bin", ".safetensors", ".onnx"]
            if model_path.suffix.lower() in model_extensions:
                # Modell sollte mindestens 10MB groß sein
                return model_path.stat().st_size > 10 * 1024 * 1024

        return True

    def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """Gibt Informationen über ein Modell zurück"""
        return self.available_models.get(model_id)

    def list_models(self) -> List[ModelInfo]:
        """Gibt Liste aller verfügbaren Modelle zurück"""
        return list(self.available_models.values())

    def is_model_downloaded(self, model_id: str) -> bool:
        """Prüft ob ein Modell heruntergeladen ist"""
        model_info = self.get_model_info(model_id)
        return model_info.downloaded if model_info else False

    @retry_on_error(max_retries=3, delay=2.0)
    def download_model(
        self,
        model_id: str,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> bool:
        """
        Lädt ein Modell herunter durch audio-separator

        Args:
            model_id: ID des Modells
            progress_callback: Callback für Progress-Updates (message, progress_percent)

        Returns:
            True wenn erfolgreich
        """
        model_info = self.get_model_info(model_id)
        if not model_info:
            logger.error(f"Unknown model: {model_id}")
            return False

        if model_info.downloaded:
            logger.info(f"Model '{model_id}' already downloaded")
            return True

        logger.info(f"Downloading model '{model_id}' ({model_info.size_mb}MB)...")

        if progress_callback:
            progress_callback(
                f"Downloading {model_info.name}... This may take several minutes.", 10
            )

        try:
            # Verwende audio-separator um das Modell herunterzuladen
            from audio_separator.separator import Separator as AudioSeparator

            if progress_callback:
                progress_callback(f"Initializing download for {model_info.name}...", 30)

            # Erstelle Separator-Instanz
            separator = AudioSeparator(
                log_level=40,  # ERROR level to suppress verbose output
                model_file_dir=str(self.models_dir),
                output_dir=str(self.models_dir),
            )

            if progress_callback:
                progress_callback(f"Downloading {model_info.name}...", 50)

            # Lade das Modell - dies löst den Download aus falls nicht vorhanden
            separator.load_model(model_filename=model_info.model_filename)

            if progress_callback:
                progress_callback(f"Verifying {model_info.name}...", 90)

            # Verifiziere dass das Modell jetzt tatsächlich vorhanden ist
            if self._verify_model(model_info.model_filename):
                model_info.downloaded = True
                model_info.path = self.models_dir / model_info.model_filename
                logger.info(f"Model '{model_id}' successfully downloaded and verified")

                if progress_callback:
                    progress_callback(
                        f"✓ {model_info.name} downloaded successfully!", 100
                    )

                return True
            else:
                logger.warning(
                    f"Model '{model_id}' download completed but verification failed"
                )
                if progress_callback:
                    progress_callback(
                        f"Download completed but model files not found", -1
                    )
                return False

        except ImportError as e:
            error_msg = "audio-separator library not installed"
            logger.error(error_msg)
            if progress_callback:
                progress_callback(error_msg, -1)
            return False

        except Exception as e:
            logger.error(f"Error downloading model '{model_id}': {e}", exc_info=True)
            if progress_callback:
                progress_callback(f"Error: {str(e)}", -1)
            return False

    def download_all_models(
        self, progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> Dict[str, bool]:
        """
        Lädt alle konfigurierten Modelle herunter

        Args:
            progress_callback: Callback für Progress-Updates

        Returns:
            Dict mit model_id -> success status
        """
        results = {}

        for i, model_id in enumerate(self.available_models.keys()):
            logger.info(
                f"Downloading model {i+1}/{len(self.available_models)}: {model_id}"
            )

            if progress_callback:
                overall_progress = int((i / len(self.available_models)) * 100)
                progress_callback(
                    f"Preparing models ({i+1}/{len(self.available_models)})",
                    overall_progress,
                )

            success = self.download_model(model_id, progress_callback)
            results[model_id] = success

        if progress_callback:
            progress_callback("All models ready", 100)

        return results

    def get_default_model(self) -> str:
        """Gibt die ID des Standard-Modells zurück"""
        return DEFAULT_MODEL

    def get_model_path(self, model_id: str) -> Optional[Path]:
        """Gibt den Pfad zu einem Modell zurück"""
        model_info = self.get_model_info(model_id)
        if model_info and model_info.downloaded:
            return model_info.path
        return None

    def delete_model(self, model_id: str) -> bool:
        """
        Löscht ein heruntergeladenes Modell

        Args:
            model_id: ID des zu löschenden Modells

        Returns:
            True wenn erfolgreich
        """
        model_info = self.get_model_info(model_id)
        if not model_info or not model_info.downloaded:
            logger.warning(f"Model '{model_id}' not downloaded, nothing to delete")
            return False

        try:
            import os

            model_path = self.models_dir / model_info.model_filename

            # Lösche die Modelldatei
            if model_path.exists():
                os.remove(model_path)

            # Für YAML-Modelle: Lösche auch die referenzierten .th-Dateien
            if model_info.model_filename.endswith(".yaml"):
                try:
                    import yaml

                    with open(model_path, "r") as f:
                        config = yaml.safe_load(f)

                    if "models" in config:
                        for model_id_ref in config["models"]:
                            for th_file in self.models_dir.glob(f"{model_id_ref}*.th"):
                                if th_file.exists():
                                    os.remove(th_file)
                                    logger.info(f"Deleted weight file: {th_file.name}")
                except Exception as e:
                    logger.warning(f"Could not delete weight files for {model_id}: {e}")

            model_info.downloaded = False
            model_info.path = None

            logger.info(f"Model '{model_id}' deleted")
            return True

        except Exception as e:
            logger.error(f"Error deleting model '{model_id}': {e}", exc_info=True)
            return False

    def get_total_size_mb(self) -> int:
        """Gibt die Gesamtgröße aller Modelle in MB zurück"""
        return sum(model.size_mb for model in self.available_models.values())

    def get_downloaded_size_mb(self) -> int:
        """Gibt die Größe aller heruntergeladenen Modelle in MB zurück"""
        return sum(
            model.size_mb
            for model in self.available_models.values()
            if model.downloaded
        )


# Globale Instanz
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Gibt die globale ModelManager-Instanz zurück"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
