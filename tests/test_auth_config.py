"""Tests for auth/auth_config.py — auth configuration management."""

import json
import os

import pytest

from auth.auth_config import (
    auth_config_exists,
    load_auth_config,
    save_auth_config,
    create_auth_config,
    update_lockout,
    reset_lockout,
    update_credential,
    delete_auth_config,
    AUTH_CONFIG_PATH,
)


class TestAuthConfigExists:
    def test_not_exists(self, project_dir):
        assert auth_config_exists() is False

    def test_exists(self, project_dir):
        os.makedirs("config", exist_ok=True)
        with open(AUTH_CONFIG_PATH, "w") as f:
            json.dump({}, f)
        assert auth_config_exists() is True


class TestLoadSave:
    def test_load_missing_returns_none(self, project_dir):
        assert load_auth_config() is None

    def test_save_and_load(self, project_dir):
        config = create_auth_config(
            credential_type="pin",
            credential_hash="$argon2id$...",
            credential_salt="base64salt==",
            recovery_email_hash="$argon2id$...",
            recovery_key_hash="$argon2id$...",
            hint="my hint",
        )
        save_auth_config(config)
        loaded = load_auth_config()

        assert loaded is not None
        assert loaded["credential_type"] == "pin"
        assert loaded["hint"] == "my hint"
        assert loaded["lockout"]["failed_attempts"] == 0

    def test_load_corrupted_returns_none(self, project_dir):
        os.makedirs("config", exist_ok=True)
        with open(AUTH_CONFIG_PATH, "w") as f:
            f.write("not json{{{")
        assert load_auth_config() is None

    def test_load_adds_missing_lockout(self, project_dir):
        os.makedirs("config", exist_ok=True)
        with open(AUTH_CONFIG_PATH, "w") as f:
            json.dump({"version": "1.0", "credential_type": "pin"}, f)
        loaded = load_auth_config()
        assert "lockout" in loaded
        assert loaded["lockout"]["failed_attempts"] == 0


class TestCreateAuthConfig:
    def test_creates_complete_config(self):
        config = create_auth_config(
            credential_type="password",
            credential_hash="hash1",
            credential_salt="salt1",
            recovery_email_hash="hash2",
            recovery_key_hash="hash3",
            hint="test hint",
        )
        assert config["version"] == "1.0"
        assert config["credential_type"] == "password"
        assert config["credential_hash"] == "hash1"
        assert config["credential_salt"] == "salt1"
        assert config["recovery_email_hash"] == "hash2"
        assert config["recovery_key_hash"] == "hash3"
        assert config["hint"] == "test hint"
        assert config["lockout"]["failed_attempts"] == 0
        assert config["lockout"]["lockout_until"] is None
        assert "created_at" in config


class TestLockout:
    def _setup_config(self, project_dir):
        config = create_auth_config("pin", "h", "s", "rh", "rkh", "hint")
        save_auth_config(config)

    def test_update_lockout(self, project_dir):
        self._setup_config(project_dir)
        update_lockout(failed_attempts=3, backoff_level=1, lockout_until="2026-01-01T00:00:00")

        loaded = load_auth_config()
        assert loaded["lockout"]["failed_attempts"] == 3
        assert loaded["lockout"]["backoff_level"] == 1
        assert loaded["lockout"]["lockout_until"] == "2026-01-01T00:00:00"
        assert loaded["lockout"]["last_failed"] is not None

    def test_reset_lockout(self, project_dir):
        self._setup_config(project_dir)
        update_lockout(5, 2, "2026-12-31T00:00:00")
        reset_lockout()

        loaded = load_auth_config()
        assert loaded["lockout"]["failed_attempts"] == 0
        assert loaded["lockout"]["backoff_level"] == 0
        assert loaded["lockout"]["lockout_until"] is None


class TestUpdateCredential:
    def test_updates_hash_and_salt(self, project_dir):
        config = create_auth_config("pin", "old_hash", "old_salt", "rh", "rkh", "hint")
        save_auth_config(config)

        update_credential("new_hash", "new_salt")
        loaded = load_auth_config()
        assert loaded["credential_hash"] == "new_hash"
        assert loaded["credential_salt"] == "new_salt"
        # Lockout should be reset
        assert loaded["lockout"]["failed_attempts"] == 0

    def test_updates_type_and_hint(self, project_dir):
        config = create_auth_config("pin", "h", "s", "rh", "rkh", "old hint")
        save_auth_config(config)

        update_credential("h2", "s2", credential_type="password", hint="new hint")
        loaded = load_auth_config()
        assert loaded["credential_type"] == "password"
        assert loaded["hint"] == "new hint"


class TestDeleteAuthConfig:
    def test_delete(self, project_dir):
        config = create_auth_config("pin", "h", "s", "rh", "rkh", "hint")
        save_auth_config(config)
        assert auth_config_exists() is True

        delete_auth_config()
        assert auth_config_exists() is False

    def test_delete_nonexistent(self, project_dir):
        # Should not raise
        delete_auth_config()
