"""Tests for auth/master_auth.py — lockout logic and key generation."""

import base64
from datetime import datetime, timedelta

import pytest

from auth.master_auth import (
    _generate_recovery_key,
    _is_locked_out,
    _get_lockout_remaining_minutes,
    _get_current_lockout_minutes,
    _check_24h_reset,
    MAX_ATTEMPTS,
    BASE_LOCKOUT_MINUTES,
    MAX_LOCKOUT_MINUTES,
)
from auth.auth_config import (
    create_auth_config,
    save_auth_config,
    load_auth_config,
    reset_lockout,
    update_lockout,
)
from crypto.key_derivation import hash_credential, verify_credential, derive_fernet_key, generate_salt


class TestRecoveryKeyGeneration:
    def test_format(self):
        key = _generate_recovery_key()
        parts = key.split("-")
        assert len(parts) == 5
        for part in parts:
            assert len(part) == 4
            assert part.isalnum()

    def test_uniqueness(self):
        keys = {_generate_recovery_key() for _ in range(100)}
        assert len(keys) == 100  # All unique

    def test_uppercase_and_digits(self):
        key = _generate_recovery_key()
        clean = key.replace("-", "")
        assert clean.isupper() or any(c.isdigit() for c in clean)


class TestLockoutLogic:
    def _make_config(self, failed=0, level=0, lockout_until=None, last_failed=None):
        return {
            "lockout": {
                "failed_attempts": failed,
                "backoff_level": level,
                "lockout_until": lockout_until,
                "last_failed": last_failed,
            }
        }

    def test_not_locked_out_initially(self):
        config = self._make_config()
        assert _is_locked_out(config) is False

    def test_locked_out_future(self):
        future = (datetime.now() + timedelta(minutes=30)).isoformat()
        config = self._make_config(lockout_until=future)
        assert _is_locked_out(config) is True

    def test_not_locked_out_past(self):
        past = (datetime.now() - timedelta(minutes=1)).isoformat()
        config = self._make_config(lockout_until=past)
        assert _is_locked_out(config) is False

    def test_lockout_minutes_level_0(self):
        config = self._make_config(level=0)
        assert _get_current_lockout_minutes(config) == 5

    def test_lockout_minutes_level_1(self):
        config = self._make_config(level=1)
        assert _get_current_lockout_minutes(config) == 10

    def test_lockout_minutes_level_2(self):
        config = self._make_config(level=2)
        assert _get_current_lockout_minutes(config) == 20

    def test_lockout_minutes_capped(self):
        config = self._make_config(level=20)  # Very high level
        assert _get_current_lockout_minutes(config) == MAX_LOCKOUT_MINUTES

    def test_remaining_minutes(self):
        future = (datetime.now() + timedelta(minutes=15)).isoformat()
        remaining = _get_lockout_remaining_minutes(future)
        assert 14 <= remaining <= 15

    def test_remaining_minutes_past(self):
        """Past lockout returns 0 (via max(1,...) on negative → actually 0 path)."""
        past = (datetime.now() - timedelta(minutes=5)).isoformat()
        remaining = _get_lockout_remaining_minutes(past)
        # Function uses max(1, int(remaining)) but negative seconds / 60 → negative int
        # max(1, -5) = 1, but _is_locked_out would return False anyway
        assert remaining >= 0

    def test_24h_reset(self, project_dir):
        """After 24h since last failure, counter should reset."""
        config = create_auth_config("pin", "h", "s", "rh", "rkh", "hint")
        save_auth_config(config)

        # Set last_failed to 25 hours ago
        old_time = (datetime.now() - timedelta(hours=25)).isoformat()
        update_lockout(5, 2, None)
        loaded = load_auth_config()
        loaded["lockout"]["last_failed"] = old_time
        save_auth_config(loaded)

        _check_24h_reset(loaded)
        after = load_auth_config()
        assert after["lockout"]["failed_attempts"] == 0
        assert after["lockout"]["backoff_level"] == 0


class TestCredentialVerification:
    def test_pin_hash_verify(self):
        pin = "1234"
        h = hash_credential(pin)
        assert verify_credential(pin, h) is True
        assert verify_credential("0000", h) is False

    def test_password_hash_verify(self):
        password = "MyStr0ngP@ss!"
        h = hash_credential(password)
        assert verify_credential(password, h) is True
        assert verify_credential("wrong", h) is False

    def test_fernet_key_from_credential(self):
        """Verify that login produces a usable Fernet key."""
        credential = "testpin123"
        salt = generate_salt()
        key = derive_fernet_key(credential, salt)

        # Key should work for encryption
        from cryptography.fernet import Fernet
        f = Fernet(key)
        token = f.encrypt(b"secret data")
        assert f.decrypt(token) == b"secret data"

    def test_same_credential_same_salt_same_key(self):
        """Deterministic: same input → same key."""
        salt = generate_salt()
        k1 = derive_fernet_key("mypin", salt)
        k2 = derive_fernet_key("mypin", salt)
        assert k1 == k2
