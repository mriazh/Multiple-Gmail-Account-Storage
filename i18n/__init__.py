"""Internationalization module for bilingual CLI output."""

from i18n import en
from i18n import id as id_lang

_LANGS = {"en": en, "id": id_lang}
_current = "en"


def set_language(lang: str) -> None:
    """Set the active language for all subsequent t() calls."""
    global _current
    if lang not in _LANGS:
        raise ValueError(f"Unsupported language: {lang}. Available: {list(_LANGS.keys())}")
    _current = lang


def get_language() -> str:
    """Get the currently active language code."""
    return _current


def t(key: str, **kwargs) -> str:
    """
    Translate a key to the current language with optional format args.

    Returns '[MISSING: key]' if the key is not found.
    """
    strings = _LANGS[_current].STRINGS
    template = strings.get(key)
    if template is None:
        return f"[MISSING: {key}]"
    return template.format(**kwargs) if kwargs else template
