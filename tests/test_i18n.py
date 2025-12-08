"""
Unit Tests für I18n System
"""

import pytest
from utils.i18n import I18n, t, set_language, get_language


@pytest.mark.unit
class TestI18n:
    """Tests für Internationalisierung"""

    def test_i18n_singleton(self):
        """Teste ob I18n ein Singleton ist"""
        i18n1 = I18n()
        i18n2 = I18n()
        assert i18n1 is i18n2

    def test_default_language(self):
        """Teste Standard-Sprache"""
        lang = get_language()
        assert lang in ["de", "en"]

    def test_set_language(self):
        """Teste Sprach-Wechsel"""
        set_language("en")
        assert get_language() == "en"

        set_language("de")
        assert get_language() == "de"

    def test_invalid_language(self):
        """Teste ungültige Sprache"""
        original = get_language()
        set_language("fr")  # Nicht verfügbar
        # Sollte bei ursprünglicher Sprache bleiben
        assert get_language() == original

    def test_translate_existing_key(self):
        """Teste Übersetzung mit existierendem Key"""
        translation = t("app.title")
        assert isinstance(translation, str)
        assert len(translation) > 0

    def test_translate_missing_key(self):
        """Teste Übersetzung mit fehlendem Key"""
        translation = t("non.existent.key", fallback="Fallback")
        assert translation == "Fallback"

    def test_translate_with_variables(self):
        """Teste Übersetzung mit Variablen"""
        # Dies setzt voraus, dass ein Key mit {version} existiert
        translation = t("app.version", version="1.0.0")
        assert "1.0.0" in translation

    def test_translate_without_fallback(self):
        """Teste Übersetzung ohne Fallback"""
        translation = t("completely.missing.key")
        # Sollte den Key selbst zurückgeben
        assert translation == "completely.missing.key"

    def test_translate_with_missing_variable(self):
        """Teste Übersetzung mit fehlender Variable"""
        # Sollte nicht crashen, auch wenn Variable fehlt
        translation = t("app.version", missing_var="test")
        assert isinstance(translation, str)

    def test_tr_alias(self):
        """Teste tr() Alias-Funktion"""
        from utils.i18n import tr

        translation = tr("app.title")
        assert isinstance(translation, str)
        assert len(translation) > 0

    def test_reload_translations(self):
        """Teste dass Übersetzungen neu geladen werden können"""
        i18n = I18n()
        original_count = len(i18n._translations)

        # Reload
        i18n._load_translations()

        assert len(i18n._translations) == original_count

    def test_get_language(self):
        """Teste get_language Funktion"""
        from utils.i18n import get_language, set_language

        set_language("de")
        assert get_language() == "de"

        set_language("en")
        assert get_language() == "en"
