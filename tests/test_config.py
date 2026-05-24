"""Tests for config_manager.py — settings management."""

import json
import os

from config_manager import (
    load_settings,
    save_settings,
    is_first_run,
    set_first_run_complete,
    get_language,
    set_language_preference,
    SETTINGS_PATH,
    DEFAULT_SETTINGS,
)


class TestLoadSettings:
    def test_returns_defaults_when_missing(self, project_dir):
        settings = load_settings()
        assert settings == DEFAULT_SETTINGS

    def test_loads_existing_file(self, project_dir):
        data = {"version": "1.0", "language": "id", "first_run_complete": True}
        os.makedirs("config", exist_ok=True)
        with open(SETTINGS_PATH, "w") as f:
            json.dump(data, f)

        settings = load_settings()
        assert settings["language"] == "id"
        assert settings["first_run_complete"] is True

    def test_handles_corrupted_json(self, project_dir):
        os.makedirs("config", exist_ok=True)
        with open(SETTINGS_PATH, "w") as f:
            f.write("{invalid json!!!")

        settings = load_settings()
        assert settings == DEFAULT_SETTINGS

    def test_fills_missing_keys(self, project_dir):
        os.makedirs("config", exist_ok=True)
        with open(SETTINGS_PATH, "w") as f:
            json.dump({"version": "1.0"}, f)

        settings = load_settings()
        assert "language" in settings
        assert "first_run_complete" in settings


class TestSaveSettings:
    def test_saves_and_loads(self, project_dir):
        data = {"version": "2.0", "language": "id", "first_run_complete": True}
        save_settings(data)

        with open(SETTINGS_PATH, "r") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_creates_config_dir(self, project_dir):
        # Remove config dir if exists
        import shutil
        if os.path.exists("config"):
            shutil.rmtree("config")

        save_settings(DEFAULT_SETTINGS)
        assert os.path.exists(SETTINGS_PATH)


class TestFirstRun:
    def test_is_first_run_no_file(self, project_dir):
        assert is_first_run() is True

    def test_is_first_run_after_setup(self, project_dir):
        set_first_run_complete()
        assert is_first_run() is False

    def test_set_first_run_complete(self, project_dir):
        set_first_run_complete()
        settings = load_settings()
        assert settings["first_run_complete"] is True


class TestLanguage:
    def test_default_language(self, project_dir):
        assert get_language() == "en"

    def test_set_language(self, project_dir):
        set_language_preference("id")
        assert get_language() == "id"

    def test_invalid_language_raises(self, project_dir):
        import pytest
        with pytest.raises(ValueError):
            set_language_preference("fr")
