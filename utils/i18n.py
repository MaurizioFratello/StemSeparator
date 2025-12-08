"""
Internationalisierungs-System für Deutsch/Englisch
"""

import json
from pathlib import Path
from typing import Optional, Dict

from config import TRANSLATIONS_DIR, DEFAULT_LANGUAGE, AVAILABLE_LANGUAGES
from utils.logger import get_logger

logger = get_logger()


class I18n:
    """Singleton für Übersetzungen"""

    _instance: Optional["I18n"] = None
    _translations: Dict[str, Dict[str, str]] = {}
    _current_language: str = DEFAULT_LANGUAGE

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._translations:
            self._load_translations()

    def _load_translations(self):
        """Lädt alle Übersetzungsdateien"""
        for lang in AVAILABLE_LANGUAGES:
            translation_file = TRANSLATIONS_DIR / f"{lang}.json"

            try:
                if translation_file.exists():
                    with open(translation_file, "r", encoding="utf-8") as f:
                        self._translations[lang] = json.load(f)
                    logger.debug(f"Loaded translations for language: {lang}")
                else:
                    logger.warning(f"Translation file not found: {translation_file}")
                    self._translations[lang] = {}
            except Exception as e:
                logger.error(f"Error loading translations for {lang}: {e}")
                self._translations[lang] = {}

    def set_language(self, language: str):
        """Setzt die aktuelle Sprache"""
        if language in AVAILABLE_LANGUAGES:
            self._current_language = language
            logger.info(f"Language set to: {language}")
        else:
            logger.warning(f"Language '{language}' not available. Using default.")

    def get_language(self) -> str:
        """Gibt die aktuelle Sprache zurück"""
        return self._current_language

    def translate(self, key: str, fallback: Optional[str] = None, **kwargs) -> str:
        """
        Übersetzt einen Key in die aktuelle Sprache

        Args:
            key: Translation key (z.B. 'app.title')
            fallback: Fallback-Text wenn Key nicht gefunden
            **kwargs: Variablen für String-Formatierung

        Returns:
            Übersetzter String
        """
        # Hole Übersetzung für aktuelle Sprache
        translation = self._translations.get(self._current_language, {}).get(key)

        # Fallback auf Englisch
        if translation is None and self._current_language != "en":
            translation = self._translations.get("en", {}).get(key)

        # Fallback auf provided fallback oder key selbst
        if translation is None:
            translation = fallback or key
            logger.debug(f"Translation missing for key: {key}")

        # String-Formatierung mit kwargs
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing variable in translation '{key}': {e}")

        return translation

    def t(self, key: str, fallback: Optional[str] = None, **kwargs) -> str:
        """Kurzform von translate()"""
        return self.translate(key, fallback, **kwargs)


# Singleton Instance
_i18n = I18n()


def set_language(language: str):
    """Setzt die Sprache"""
    _i18n.set_language(language)


def get_language() -> str:
    """Gibt aktuelle Sprache zurück"""
    return _i18n.get_language()


def t(key: str, fallback: Optional[str] = None, **kwargs) -> str:
    """
    Übersetzt einen Text

    Usage:
        from utils.i18n import t
        title = t('app.title')
        msg = t('file.processing', filename='song.mp3')
    """
    return _i18n.translate(key, fallback, **kwargs)


def tr(key: str, fallback: Optional[str] = None, **kwargs) -> str:
    """Alias für t() (translate)"""
    return t(key, fallback, **kwargs)


if __name__ == "__main__":
    # Test
    print(f"Current language: {get_language()}")
    print(f"Translation test: {t('app.title', 'Stem Separator')}")

    set_language("en")
    print(f"After switching to EN: {t('app.title', 'Stem Separator')}")
