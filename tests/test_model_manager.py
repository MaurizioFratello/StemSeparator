"""
Unit Tests für Model Manager
"""
import pytest
from pathlib import Path
import tempfile
import shutil

from core.model_manager import ModelManager, ModelInfo, get_model_manager
from config import MODELS, DEFAULT_MODEL


@pytest.fixture
def temp_models_dir():
    """Erstellt temporäres Modell-Verzeichnis"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def model_manager_with_temp_dir(temp_models_dir, monkeypatch):
    """ModelManager mit temporärem Verzeichnis"""
    # Setze MODELS_DIR auf temp dir
    monkeypatch.setattr('core.model_manager.MODELS_DIR', temp_models_dir)

    # Erstelle neue ModelManager-Instanz
    manager = ModelManager()
    return manager


@pytest.mark.unit
class TestModelInfo:
    """Tests für ModelInfo Dataclass"""

    def test_model_info_creation(self):
        """Teste ModelInfo Erstellung"""
        info = ModelInfo(
            name="Test Model",
            stems=4,
            size_mb=100,
            description="Test",
            model_filename="test_model.onnx",
            backend="test_backend"
        )

        assert info.name == "Test Model"
        assert info.stems == 4
        assert info.size_mb == 100
        assert info.downloaded is False
        assert info.path is None


@pytest.mark.unit
class TestModelManager:
    """Tests für Model Manager"""

    def test_initialization(self, model_manager_with_temp_dir):
        """Teste ModelManager Initialisierung"""
        manager = model_manager_with_temp_dir

        assert manager.models_dir.exists()
        assert len(manager.available_models) > 0

    def test_load_model_info(self, model_manager_with_temp_dir):
        """Teste dass alle konfigurierten Modelle geladen werden"""
        manager = model_manager_with_temp_dir

        # Alle Modelle aus config sollten vorhanden sein
        for model_id in MODELS.keys():
            assert model_id in manager.available_models

    def test_get_model_info_existing(self, model_manager_with_temp_dir):
        """Teste get_model_info für existierendes Modell"""
        manager = model_manager_with_temp_dir

        # Hole erstes Modell aus config
        first_model_id = list(MODELS.keys())[0]
        info = manager.get_model_info(first_model_id)

        assert info is not None
        assert isinstance(info, ModelInfo)
        assert info.name == MODELS[first_model_id]['name']

    def test_get_model_info_nonexistent(self, model_manager_with_temp_dir):
        """Teste get_model_info für nicht-existierendes Modell"""
        manager = model_manager_with_temp_dir

        info = manager.get_model_info('nonexistent_model')
        assert info is None

    def test_list_models(self, model_manager_with_temp_dir):
        """Teste list_models"""
        manager = model_manager_with_temp_dir

        models = manager.list_models()

        assert isinstance(models, list)
        assert len(models) == len(MODELS)
        assert all(isinstance(m, ModelInfo) for m in models)

    def test_is_model_downloaded_false(self, model_manager_with_temp_dir):
        """Teste is_model_downloaded für nicht-heruntergeladenes Modell"""
        manager = model_manager_with_temp_dir

        first_model_id = list(MODELS.keys())[0]
        assert manager.is_model_downloaded(first_model_id) is False

    def test_is_model_downloaded_true(self, model_manager_with_temp_dir):
        """Teste is_model_downloaded für heruntergeladenes Modell"""
        manager = model_manager_with_temp_dir

        # Simuliere heruntergeladenes Modell
        first_model_id = list(MODELS.keys())[0]
        model_path = manager.models_dir / first_model_id
        model_path.mkdir(parents=True, exist_ok=True)
        (model_path / "test_file.txt").write_text("test")

        # Reload model info
        manager._load_model_info()

        assert manager.is_model_downloaded(first_model_id) is True

    def test_verify_model_nonexistent(self, model_manager_with_temp_dir):
        """Teste _verify_model für nicht-existierendes Modell"""
        manager = model_manager_with_temp_dir

        result = manager._verify_model(Path("/nonexistent/path"))
        assert result is False

    def test_verify_model_empty_dir(self, model_manager_with_temp_dir):
        """Teste _verify_model für leeres Verzeichnis"""
        manager = model_manager_with_temp_dir

        empty_dir = manager.models_dir / "empty"
        empty_dir.mkdir()

        result = manager._verify_model(empty_dir)
        assert result is False

    def test_verify_model_valid_dir(self, model_manager_with_temp_dir):
        """Teste _verify_model für gültiges Verzeichnis"""
        manager = model_manager_with_temp_dir

        valid_dir = manager.models_dir / "valid"
        valid_dir.mkdir()
        (valid_dir / "model.pth").write_text("dummy")

        result = manager._verify_model(valid_dir)
        assert result is True

    def test_download_model(self, model_manager_with_temp_dir):
        """Teste download_model"""
        manager = model_manager_with_temp_dir

        first_model_id = list(MODELS.keys())[0]

        # Track progress callbacks
        progress_calls = []

        def progress_callback(message, percent):
            progress_calls.append((message, percent))

        result = manager.download_model(first_model_id, progress_callback)

        assert result is True
        assert manager.is_model_downloaded(first_model_id) is True
        assert len(progress_calls) >= 2  # Mindestens Start und Ende

    def test_download_model_already_downloaded(self, model_manager_with_temp_dir):
        """Teste download_model für bereits heruntergeladenes Modell"""
        manager = model_manager_with_temp_dir

        first_model_id = list(MODELS.keys())[0]

        # Erster Download
        manager.download_model(first_model_id)

        # Zweiter Download sollte sofort True zurückgeben
        result = manager.download_model(first_model_id)
        assert result is True

    def test_download_model_unknown(self, model_manager_with_temp_dir):
        """Teste download_model für unbekanntes Modell"""
        manager = model_manager_with_temp_dir

        result = manager.download_model('unknown_model')
        assert result is False

    def test_download_all_models(self, model_manager_with_temp_dir):
        """Teste download_all_models"""
        manager = model_manager_with_temp_dir

        results = manager.download_all_models()

        assert isinstance(results, dict)
        assert len(results) == len(MODELS)
        # Alle sollten erfolgreich sein
        assert all(results.values())

    def test_get_default_model(self, model_manager_with_temp_dir):
        """Teste get_default_model"""
        manager = model_manager_with_temp_dir

        default = manager.get_default_model()
        assert default == DEFAULT_MODEL
        assert default in MODELS

    def test_get_model_path_not_downloaded(self, model_manager_with_temp_dir):
        """Teste get_model_path für nicht-heruntergeladenes Modell"""
        manager = model_manager_with_temp_dir

        first_model_id = list(MODELS.keys())[0]
        path = manager.get_model_path(first_model_id)

        assert path is None

    def test_get_model_path_downloaded(self, model_manager_with_temp_dir):
        """Teste get_model_path für heruntergeladenes Modell"""
        manager = model_manager_with_temp_dir

        first_model_id = list(MODELS.keys())[0]
        manager.download_model(first_model_id)

        path = manager.get_model_path(first_model_id)
        assert path is not None
        assert path.exists()

    def test_delete_model_not_downloaded(self, model_manager_with_temp_dir):
        """Teste delete_model für nicht-heruntergeladenes Modell"""
        manager = model_manager_with_temp_dir

        first_model_id = list(MODELS.keys())[0]
        result = manager.delete_model(first_model_id)

        assert result is False

    def test_delete_model_success(self, model_manager_with_temp_dir):
        """Teste delete_model für heruntergeladenes Modell"""
        manager = model_manager_with_temp_dir

        first_model_id = list(MODELS.keys())[0]

        # Download first
        manager.download_model(first_model_id)
        assert manager.is_model_downloaded(first_model_id) is True

        # Delete
        result = manager.delete_model(first_model_id)

        assert result is True
        assert manager.is_model_downloaded(first_model_id) is False

    def test_get_total_size_mb(self, model_manager_with_temp_dir):
        """Teste get_total_size_mb"""
        manager = model_manager_with_temp_dir

        total_size = manager.get_total_size_mb()

        # Sollte Summe aller Modell-Größen sein
        expected_size = sum(m['size_mb'] for m in MODELS.values())
        assert total_size == expected_size

    def test_get_downloaded_size_mb(self, model_manager_with_temp_dir):
        """Teste get_downloaded_size_mb"""
        manager = model_manager_with_temp_dir

        # Anfangs 0
        assert manager.get_downloaded_size_mb() == 0

        # Nach Download eines Modells
        first_model_id = list(MODELS.keys())[0]
        manager.download_model(first_model_id)

        expected_size = MODELS[first_model_id]['size_mb']
        assert manager.get_downloaded_size_mb() == expected_size

    def test_get_model_manager_singleton(self):
        """Teste get_model_manager Singleton-Funktion"""
        manager1 = get_model_manager()
        manager2 = get_model_manager()

        assert manager1 is manager2
        assert isinstance(manager1, ModelManager)
