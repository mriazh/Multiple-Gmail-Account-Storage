"""Configuration and settings management for Gmail Account Manager."""

import json
import os

from utils import atomic_write_json

SETTINGS_PATH = os.path.join("config", "settings.json")

DEFAULT_SETTINGS = {
    "version": "1.0",
    "language": "en",
    "first_run_complete": False,
}


def _ensure_config_dir():
    """Ensure the config/ directory exists."""
    os.makedirs("config", exist_ok=True)


def load_settings() -> dict:
    """
    Load settings from config/settings.json.
    Returns default settings if file is missing or corrupted.
    """
    _ensure_config_dir()
    if not os.path.exists(SETTINGS_PATH):
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Validate required keys exist
        for key in DEFAULT_SETTINGS:
            if key not in data:
                data[key] = DEFAULT_SETTINGS[key]
        return data
    except (json.JSONDecodeError, OSError):
        # Corrupted file — return defaults
        return DEFAULT_SETTINGS.copy()


def save_settings(data: dict) -> None:
    """Save settings to config/settings.json atomically."""
    _ensure_config_dir()
    atomic_write_json(SETTINGS_PATH, data)


def is_first_run() -> bool:
    """Check if this is the first run (no setup completed yet)."""
    settings = load_settings()
    return not settings.get("first_run_complete", False)


def set_first_run_complete() -> None:
    """Mark first-time setup as complete."""
    settings = load_settings()
    settings["first_run_complete"] = True
    save_settings(settings)


def get_language() -> str:
    """Get the stored language preference."""
    settings = load_settings()
    return settings.get("language", "en")


def set_language_preference(lang: str) -> None:
    """Store the language preference."""
    if lang not in ("en", "id"):
        raise ValueError(f"Unsupported language: {lang}")
    settings = load_settings()
    settings["language"] = lang
    save_settings(settings)
