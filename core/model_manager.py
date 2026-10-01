"""
Model manager for downloading and validating separation models.

WHY: model weights are not confined to one directory. They can be shipped
inside the (read-only) app bundle, downloaded into the writable model
directory chosen by `config`, or left behind by audio-separator itself in
`~/.audio-separator/models` by earlier runs or other tools. Every lookup
therefore walks `config.MODEL_SEARCH_PATHS` so an already installed model is
reported as available instead of being re-downloaded, while every write keeps
targeting the single writable directory (`config.MODELS_DIR`).
"""

import os
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional
from dataclasses import dataclass

# WHY: `MODELS_DIR`, `MODEL_SEARCH_PATHS` and `BUNDLED_MODELS_DIR` are imported
# into this module's namespace on purpose: `tests/test_model_manager.py`
# monkeypatches `core.model_manager.MODELS_DIR`, and nothing else may read them
# directly — only through the resolver functions below, which look the globals
# up at call time so a monkeypatch (or a late `config` bootstrap) takes effect.
from config import (
    MODELS,
    DEFAULT_MODEL,
    MODELS_DIR,
    MODEL_SEARCH_PATHS,
    BUNDLED_MODELS_DIR,
)
from utils.logger import get_logger
from utils.error_handler import retry_on_error

logger = get_logger()

# Smallest size we accept for a weight file; anything smaller is a truncated
# or placeholder download (audio-separator writes partial files as *.part, but
# an interrupted run can also leave a stub behind).
MIN_MODEL_BYTES = 10 * 1024 * 1024

# Weight file extensions that get the size sanity check.
MODEL_EXTENSIONS = (".pth", ".pt", ".ckpt", ".bin", ".safetensors", ".onnx")

# Label used when a model was found somewhere we neither own nor bundle.
EXTERNAL_SOURCE_LABEL = "external"


def audio_separator_home_dir() -> Path:
    """
    Directory audio-separator falls back to when `model_file_dir` is unused.

    WHY: resolved lazily (not at import) so tests can redirect `Path.home()`
    and so a relocated home directory is picked up without re-importing.
    """
    return Path.home() / ".audio-separator" / "models"


def writable_models_dir() -> Path:
    """
    Directory every model download and write must target.

    WHY: read the module global on each call — binding it once in `__init__`
    would freeze the value and defeat the documented monkeypatch seam.
    """
    return Path(MODELS_DIR)


def ensure_writable_models_dir() -> bool:
    """
    Create the writable model directory, reporting failure instead of raising.

    WHY: a read-only install (or an unwritable user cache) must not crash app
    start-up — same tolerance `config.py` applies to its own directory setup.
    Callers that actually write check the return value and surface the error
    where the user can act on it.
    """
    target = writable_models_dir()
    try:
        target.mkdir(parents=True, exist_ok=True)
        return True
    except OSError as error:
        logger.warning(f"Models directory {target} is not writable: {error}")
        return False


def model_search_dirs() -> List[Path]:
    """
    All directories consulted when looking for model weights, in priority order.

    WHY: `config.MODEL_SEARCH_PATHS` owns the precedence (bundled first, then
    the writable directory). The writable directory and audio-separator's own
    cache are appended defensively so a lookup never misses the place downloads
    land in, even if `config` handed us a stale/short list; duplicates are
    collapsed while the order is preserved.
    """
    candidates: List[Path] = [Path(path) for path in MODEL_SEARCH_PATHS]
    candidates.append(writable_models_dir())
    candidates.append(audio_separator_home_dir())

    ordered: List[Path] = []
    seen: set = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(candidate)
    return ordered


def source_label_for(directory: Path) -> str:
    """Human-readable origin of a directory, used in logs and status reports."""
    if directory is None:
        return ""
    if directory == writable_models_dir():
        return "writable"
    if directory == Path(BUNDLED_MODELS_DIR):
        return "bundled"
    if directory == audio_separator_home_dir():
        return "audio-separator"
    return EXTERNAL_SOURCE_LABEL


def _demucs_bundle_is_complete(yaml_path: Path) -> bool:
    """
    Check a Demucs YAML descriptor together with the weights it references.

    WHY: the weights must sit next to the YAML. audio-separator resolves both
    relative to the single `model_file_dir` it is handed, so a bundle split
    across directories would report "available" here and then fail (or silently
    re-download) when separation actually starts.
    """
    try:
        import yaml

        with open(yaml_path, "r") as handle:
            model_config = yaml.safe_load(handle)

        if "models" in model_config:
            weights_dir = yaml_path.parent
            for model_id in model_config["models"]:
                # Look for the .th weight files belonging to this model id
                matching_files = list(weights_dir.glob(f"{model_id}*.th"))
                if not matching_files:
                    return False

                for th_file in matching_files:
                    if th_file.stat().st_size < MIN_MODEL_BYTES:
                        return False

        return True
    except Exception as error:
        logger.warning(f"Error verifying YAML model {yaml_path.name}: {error}")
        return False


def _candidate_is_valid(model_path: Path) -> bool:
    """
    Decide whether one located candidate is usable.

    Mirrors the historical `_verify_model` rules: missing file or undersized
    weight is rejected, a Demucs YAML needs its weights beside it.
    """
    try:
        if not model_path.exists():
            return False

        if model_path.name.endswith(".yaml"):
            return _demucs_bundle_is_complete(model_path)

        if model_path.suffix.lower() in MODEL_EXTENSIONS:
            return model_path.stat().st_size > MIN_MODEL_BYTES
    except OSError as error:
        logger.warning(f"Error verifying model candidate {model_path}: {error}")
        return False

    return True


def find_model_file(
    model_filename: str, search_dirs: Optional[Iterable[Path]] = None
) -> Optional[Path]:
    """
    Locate one model file across every candidate directory.

    Args:
        model_filename: bare file name as declared in `config.MODELS`
        search_dirs: override the search order (defaults to `model_search_dirs()`)

    Returns:
        Path of the first complete/valid copy found, or None when absent.
    """
    directories = model_search_dirs() if search_dirs is None else list(search_dirs)

    for directory in directories:
        try:
            if not directory.is_dir():
                continue
        except OSError as error:
            logger.warning(f"Could not inspect model directory {directory}: {error}")
            continue

        candidate = directory / model_filename
        if _candidate_is_valid(candidate):
            return candidate

    return None


@dataclass
class ModelInfo:
    """Static metadata plus the on-disk location of one model."""

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
    # WHY: `path` alone cannot tell a bundled weight from a downloaded one, and
    # the UI/status output needs to say which directory it came from.
    source_dir: Optional[Path] = None  # directory the located file lives in
    source_label: str = ""  # "writable" | "bundled" | "audio-separator" | "external"

    @property
    def is_bundled(self) -> bool:
        """True when the model was found in the read-only app bundle."""
        return self.source_label == "bundled"


class ModelManager:
    """Manages the audio separation models (lookup, download, deletion)."""

    def __init__(self):
        # WHY: directory creation is guarded (try/except in `ensure_models_dir`)
        # so a read-only install only warns instead of aborting app start-up.
        self.ensure_models_dir()
        self.available_models: Dict[str, ModelInfo] = {}
        self._load_model_info()
        logger.info("ModelManager initialized")

    @property
    def models_dir(self) -> Path:
        """
        Writable directory all model writes target.

        WHY: a property resolving `MODELS_DIR` at call time, so existing callers
        keep working while monkeypatching the module global still takes effect.
        """
        return writable_models_dir()

    @property
    def search_dirs(self) -> List[Path]:
        """Directories consulted for model lookups, in priority order."""
        return model_search_dirs()

    def ensure_models_dir(self) -> bool:
        """Create the writable model directory; False when it stays unusable."""
        return ensure_writable_models_dir()

    def _load_model_info(self):
        """Collects the metadata of every configured model and its on-disk state."""
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

            self._mark_located(model_id, model_info)
            self.available_models[model_id] = model_info

    def _mark_located(self, model_id: str, model_info: ModelInfo) -> bool:
        """
        Refresh one model's availability from the search paths.

        Returns:
            True when a usable copy was found (and recorded on `model_info`).
        """
        located = self._locate_model(model_info.model_filename)
        return self._set_location(model_id, model_info, located)

    def _set_location(
        self, model_id: str, model_info: ModelInfo, located: Optional[Path]
    ) -> bool:
        """
        Record where a model was found, or that it is missing.

        WHY: `path` and the origin pair (`source_dir`/`source_label`) must never
        disagree, so every writer of that state funnels through this method.
        """
        if located is None:
            model_info.downloaded = False
            model_info.path = None
            model_info.source_dir = None
            model_info.source_label = ""
            logger.info(f"Model '{model_id}' not downloaded")
            return False

        model_info.downloaded = True
        model_info.path = located
        model_info.source_dir = located.parent
        model_info.source_label = source_label_for(located.parent)
        logger.info(
            f"Model '{model_id}' found and verified "
            f"({model_info.source_label}: {located})"
        )
        return True

    def _locate_model(self, model_filename: str) -> Optional[Path]:
        """
        Find a model file in any search directory.

        WHY: audio-separator stores models flat inside a model directory (no
        per-model subfolders). Demucs YAMLs additionally need their `.th` weight
        files to be present in the same directory.
        """
        return find_model_file(model_filename, self.search_dirs)

    def _verify_model(self, model_filename: str) -> bool:
        """
        Compatibility wrapper: True when a usable copy exists somewhere.

        Kept because callers and tests predate the multi-directory lookup; new
        code should use `_locate_model()` to get the location as well.
        """
        return self._locate_model(model_filename) is not None

    def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """Returns the metadata of one model"""
        return self.available_models.get(model_id)

    def list_models(self) -> List[ModelInfo]:
        """Returns a list of all configured models"""
        return list(self.available_models.values())

    def is_model_downloaded(self, model_id: str) -> bool:
        """Checks whether a model is available on disk"""
        model_info = self.get_model_info(model_id)
        return model_info.downloaded if model_info else False

    def get_downloaded_models(self) -> List[str]:
        """Model ids whose weights were found on disk (any search directory)"""
        return [
            model_id
            for model_id, model_info in self.available_models.items()
            if model_info.downloaded
        ]

    def get_missing_models(self) -> List[str]:
        """Model ids that still need to be downloaded into `models_dir`"""
        return [
            model_id
            for model_id, model_info in self.available_models.items()
            if not model_info.downloaded
        ]

    def refresh(self, model_id: Optional[str] = None) -> None:
        """
        Re-run the availability lookup (e.g. after an external copy-in).

        Args:
            model_id: refresh only this model, or every model when None
        """
        if model_id is None:
            self._load_model_info()
            return

        model_info = self.get_model_info(model_id)
        if model_info:
            self._mark_located(model_id, model_info)

    @retry_on_error(max_retries=3, delay=2.0)
    def download_model(
        self,
        model_id: str,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> bool:
        """
        Downloads a model via audio-separator.

        Args:
            model_id: ID of the model
            progress_callback: callback for progress updates (message, progress_percent)

        Returns:
            True when the model ended up available
        """
        model_info = self.get_model_info(model_id)
        if not model_info:
            logger.error(f"Unknown model: {model_id}")
            return False

        if model_info.downloaded:
            # WHY: the cached state can be stale (weights removed or moved
            # externally). Re-check the recorded path instead of promising a
            # download that never happens.
            if model_info.path is not None and _candidate_is_valid(model_info.path):
                logger.info(
                    f"Model '{model_id}' already available "
                    f"({model_info.source_label}: {model_info.path})"
                )
                return True
            self._set_location(model_id, model_info, None)

        # WHY: re-check the search paths right before downloading — weights may
        # have appeared since `__init__` (manual copy, another tool, a model
        # manager in another process) and must not be fetched a second time.
        if self._mark_located(model_id, model_info):
            if progress_callback:
                progress_callback(
                    f"✓ {model_info.name} already available "
                    f"({model_info.source_label})",
                    100,
                )
            return True

        # Every write goes to the writable directory only: the bundled app dir
        # is read-only in packaged builds (Program Files / _MEIPASS).
        if not self.ensure_models_dir():
            error_msg = (
                f"Models directory {self.models_dir} is not writable; "
                f"cannot download {model_info.name}"
            )
            logger.error(error_msg)
            if progress_callback:
                progress_callback(error_msg, -1)
            return False
        target_dir = self.models_dir

        logger.info(f"Downloading model '{model_id}' ({model_info.size_mb}MB)...")

        if progress_callback:
            progress_callback(
                f"Downloading {model_info.name}... This may take several minutes.", 10
            )

        try:
            # Use audio-separator to download the model
            from audio_separator.separator import Separator as AudioSeparator

            if progress_callback:
                progress_callback(f"Initializing download for {model_info.name}...", 30)

            # Create separator instance
            separator = AudioSeparator(
                log_level=40,  # ERROR level to suppress verbose output
                model_file_dir=str(target_dir),
                output_dir=str(target_dir),
            )

            if progress_callback:
                progress_callback(f"Downloading {model_info.name}...", 50)

            # Load the model - this triggers the download when absent
            separator.load_model(model_filename=model_info.model_filename)

            if progress_callback:
                progress_callback(f"Verifying {model_info.name}...", 90)

            # Verify the model is really there now; prefer the freshly
            # downloaded copy so `path` points at the file we control.
            downloaded_candidate = target_dir / model_info.model_filename
            located = (
                downloaded_candidate
                if _candidate_is_valid(downloaded_candidate)
                else self._locate_model(model_info.model_filename)
            )

            if self._set_location(model_id, model_info, located):
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
        Downloads all configured models

        Args:
            progress_callback: callback for progress updates

        Returns:
            Dict with model_id -> success status
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
        """Returns the ID of the default model"""
        return DEFAULT_MODEL

    def get_model_path(self, model_id: str) -> Optional[Path]:
        """Returns the path to a model (may point at a read-only search dir)"""
        model_info = self.get_model_info(model_id)
        if model_info and model_info.downloaded:
            return model_info.path
        return None

    def get_model_dir(self, model_id: str) -> Optional[Path]:
        """
        Directory to hand to audio-separator as `model_file_dir` for a model.

        Returns:
            The directory holding the weights, or None when unavailable.
        """
        model_info = self.get_model_info(model_id)
        if model_info and model_info.downloaded:
            return model_info.source_dir
        return None

    def delete_model(self, model_id: str) -> bool:
        """
        Deletes a downloaded model.

        Args:
            model_id: ID of the model to delete

        Returns:
            True when successful
        """
        model_info = self.get_model_info(model_id)
        if not model_info or not model_info.downloaded:
            logger.warning(f"Model '{model_id}' not downloaded, nothing to delete")
            return False

        target_dir = self.models_dir

        # WHY: only this application's writable directory may be cleaned. The
        # bundled model dir is read-only (and re-populated by the installer), and
        # ~/.audio-separator/models is shared with other tools — deleting there
        # would destroy caches the user relies on elsewhere.
        if model_info.source_dir is not None and model_info.source_dir != target_dir:
            logger.warning(
                f"Model '{model_id}' lives in {model_info.source_dir} "
                f"({model_info.source_label}); only {target_dir} is deletable"
            )
            return False

        try:
            model_path = target_dir / model_info.model_filename

            # Delete the model file
            if model_path.exists():
                os.remove(model_path)

            # For YAML models: also delete the referenced .th files
            if model_info.model_filename.endswith(".yaml"):
                try:
                    import yaml

                    with open(model_path, "r") as handle:
                        model_config = yaml.safe_load(handle)

                    if "models" in model_config:
                        for model_id_ref in model_config["models"]:
                            for th_file in target_dir.glob(f"{model_id_ref}*.th"):
                                if th_file.exists():
                                    os.remove(th_file)
                                    logger.info(f"Deleted weight file: {th_file.name}")
                except Exception as e:
                    logger.warning(f"Could not delete weight files for {model_id}: {e}")

            self._set_location(model_id, model_info, None)

            logger.info(f"Model '{model_id}' deleted")
            return True

        except Exception as e:
            logger.error(f"Error deleting model '{model_id}': {e}", exc_info=True)
            return False

    def get_total_size_mb(self) -> int:
        """Returns the total size of all models in MB"""
        return sum(model.size_mb for model in self.available_models.values())

    def get_downloaded_size_mb(self) -> int:
        """Returns the size of all available models in MB"""
        return sum(
            model.size_mb
            for model in self.available_models.values()
            if model.downloaded
        )

    def get_status(self, model_id: str) -> Dict[str, object]:
        """
        Returns a plain-dict status snapshot of one model.

        WHY: the UI and diagnostic output need the origin directory as well, and
        dict access is easier to extend than another positional return. All
        pre-existing keys keep their meaning.
        """
        model_info = self.get_model_info(model_id)
        if not model_info:
            return {}

        return {
            "model_id": model_id,
            "name": model_info.name,
            "stems": model_info.stems,
            "size_mb": model_info.size_mb,
            "backend": model_info.backend,
            "model_filename": model_info.model_filename,
            "downloaded": model_info.downloaded,
            "path": model_info.path,
            "source_dir": model_info.source_dir,
            "source_label": model_info.source_label,
            "download_dir": self.models_dir,
            "search_dirs": self.search_dirs,
        }


# Global instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Returns the global ModelManager instance"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
