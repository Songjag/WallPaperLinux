"""Runtime-editable UI translations loaded from JSON."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path


class TranslationError(RuntimeError):
    """Raised when the editable translation file cannot be used."""


class Translator:
    """Load translations and format messages for the selected language."""

    def __init__(self, source: Path, language: str = "vi") -> None:
        self.source = source
        self.text = self._load()
        self.language = language if language in self.text else next(iter(self.text))

    def _load(self) -> dict[str, dict[str, str]]:
        try:
            data = json.loads(self.source.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise TranslationError(f"Translation file not found: {self.source}") from error
        except json.JSONDecodeError as error:
            raise TranslationError(f"Invalid translation JSON: {error}") from error
        if not isinstance(data, Mapping) or not data:
            raise TranslationError("The translation JSON must contain at least one language.")
        translations: dict[str, dict[str, str]] = {}
        for code, messages in data.items():
            if not isinstance(code, str) or not isinstance(messages, Mapping):
                raise TranslationError("Each language must be an object of string messages.")
            translations[code] = {
                key: value for key, value in messages.items() if isinstance(key, str) and isinstance(value, str)
            }
        return translations

    def set_language(self, language: str) -> None:
        if language not in self.text:
            raise TranslationError(f"Unknown language: {language}")
        self.language = language

    def t(self, key: str, **values: object) -> str:
        message = self.text.get(self.language, {}).get(key) or self.text.get("en", {}).get(key)
        if message is None:
            return key
        try:
            return message.format(**values)
        except (KeyError, ValueError):
            return message
