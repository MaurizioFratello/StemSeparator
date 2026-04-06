import importlib
from pathlib import Path


def test_windows_user_dir_prefers_localappdata(monkeypatch):
    import config

    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\tester\AppData\Local")

    user_dir = config.get_user_dir()
    assert str(user_dir).endswith("StemSeparator")
    assert "AppData" in str(user_dir)


def test_models_dir_is_writable_user_path():
    import config

    assert config.MODELS_DIR.is_absolute()
    assert config.MODELS_DIR.name == "models"
    assert config.MODELS_DIR.parent == config.USER_DIR


def test_main_imports_without_platform_specific_lock_crash():
    module = importlib.import_module("main")
    assert hasattr(module, "acquire_lock")
    assert callable(module.acquire_lock)


def test_macos_user_dir_unchanged_when_frozen(monkeypatch):
    import config

    monkeypatch.setattr(config.sys, "platform", "darwin")
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)

    user_dir = config.get_user_dir()
    expected = Path.home() / "Library" / "Application Support" / "StemSeparator"
    assert user_dir == expected
