"""Tests for accounts/credential_store.py — encrypted credential storage."""

import json
import os

import pytest
from cryptography.fernet import Fernet

from accounts.credential_store import (
    load,
    save,
    get_groups,
    get_emails,
    get_group_count,
    add,
    remove,
    update_password,
    decrypt_password,
    email_exists,
    check_gitignore_warning,
    ACCOUNTS_PATH,
)
from crypto.key_derivation import generate_salt, derive_fernet_key


@pytest.fixture
def fernet_key():
    """Generate a valid Fernet key for testing."""
    salt = generate_salt()
    return derive_fernet_key("test_password", salt)


class TestLoadSave:
    def test_load_empty(self, project_dir):
        data = load()
        assert data == {}

    def test_save_and_load(self, project_dir):
        data = {"Group_1": [{"email": "a@b.com", "password": "enc", "salt": "s"}]}
        save(data)
        loaded = load()
        assert loaded == data

    def test_load_corrupted(self, project_dir):
        with open(ACCOUNTS_PATH, "w") as f:
            f.write("not json{{{")
        assert load() == {}


class TestAddRemove:
    def test_add_account(self, project_dir, fernet_key):
        add("Group_1", "test@gmail.com", "password123", fernet_key)

        data = load()
        assert "Group_1" in data
        assert len(data["Group_1"]) == 1
        assert data["Group_1"][0]["email"] == "test@gmail.com"
        # Password should be encrypted (not plaintext)
        assert data["Group_1"][0]["password"] != "password123"
        assert "salt" in data["Group_1"][0]

    def test_add_multiple_accounts(self, project_dir, fernet_key):
        add("Group_1", "a@gmail.com", "pass1", fernet_key)
        add("Group_1", "b@gmail.com", "pass2", fernet_key)
        add("Group_1", "c@gmail.com", "pass3", fernet_key)

        assert get_group_count("Group_1") == 3

    def test_add_duplicate_raises(self, project_dir, fernet_key):
        add("Group_1", "dup@gmail.com", "pass", fernet_key)
        with pytest.raises(ValueError, match="already exists"):
            add("Group_1", "dup@gmail.com", "pass2", fernet_key)

    def test_add_case_insensitive_duplicate(self, project_dir, fernet_key):
        add("Group_1", "Test@Gmail.com", "pass", fernet_key)
        with pytest.raises(ValueError, match="already exists"):
            add("Group_1", "test@gmail.com", "pass2", fernet_key)

    def test_add_exceeds_capacity(self, project_dir, fernet_key):
        for i in range(5):
            add("Full", f"user{i}@gmail.com", f"pass{i}", fernet_key)
        with pytest.raises(ValueError, match="full"):
            add("Full", "extra@gmail.com", "pass", fernet_key)

    def test_remove_account(self, project_dir, fernet_key):
        add("Group_1", "remove@gmail.com", "pass", fernet_key)
        remove("Group_1", "remove@gmail.com")
        assert get_group_count("Group_1") == 0

    def test_remove_nonexistent_raises(self, project_dir, fernet_key):
        add("Group_1", "exists@gmail.com", "pass", fernet_key)
        with pytest.raises(ValueError, match="not found"):
            remove("Group_1", "nope@gmail.com")

    def test_remove_from_nonexistent_group(self, project_dir):
        with pytest.raises(ValueError, match="not found"):
            remove("NoGroup", "a@b.com")

    def test_remove_deletes_empty_group(self, project_dir, fernet_key):
        add("Temp", "only@gmail.com", "pass", fernet_key)
        remove("Temp", "only@gmail.com")
        data = load()
        assert "Temp" not in data


class TestDecryptPassword:
    def test_decrypt_roundtrip(self, project_dir, fernet_key):
        add("Group_1", "user@gmail.com", "MySecret123!", fernet_key)
        decrypted = decrypt_password("Group_1", "user@gmail.com", fernet_key)
        assert decrypted == "MySecret123!"

    def test_decrypt_unicode_password(self, project_dir, fernet_key):
        add("Group_1", "uni@gmail.com", "пароль🔑", fernet_key)
        decrypted = decrypt_password("Group_1", "uni@gmail.com", fernet_key)
        assert decrypted == "пароль🔑"


class TestUpdatePassword:
    def test_update_password(self, project_dir, fernet_key):
        add("Group_1", "user@gmail.com", "old_pass", fernet_key)
        update_password("Group_1", "user@gmail.com", "new_pass", fernet_key)
        decrypted = decrypt_password("Group_1", "user@gmail.com", fernet_key)
        assert decrypted == "new_pass"

    def test_update_nonexistent_raises(self, project_dir, fernet_key):
        with pytest.raises(ValueError):
            update_password("Group_1", "nope@gmail.com", "pass", fernet_key)


class TestQueries:
    def test_get_groups(self, project_dir, fernet_key):
        add("Alpha", "a@gmail.com", "p", fernet_key)
        add("Beta", "b@gmail.com", "p", fernet_key)
        groups = get_groups()
        assert "Alpha" in groups
        assert "Beta" in groups

    def test_get_emails(self, project_dir, fernet_key):
        add("G", "x@gmail.com", "p", fernet_key)
        add("G", "y@gmail.com", "p", fernet_key)
        emails = get_emails("G")
        assert "x@gmail.com" in emails
        assert "y@gmail.com" in emails

    def test_get_emails_empty_group(self, project_dir):
        assert get_emails("Empty") == []

    def test_email_exists(self, project_dir, fernet_key):
        add("G", "check@gmail.com", "p", fernet_key)
        assert email_exists("G", "check@gmail.com") is True
        assert email_exists("G", "CHECK@GMAIL.COM") is True
        assert email_exists("G", "other@gmail.com") is False


class TestGitignoreCheck:
    def test_gitignore_with_accounts(self, project_dir):
        with open(".gitignore", "w") as f:
            f.write("accounts.json\n*.pyc\n")
        assert check_gitignore_warning() is True

    def test_gitignore_without_accounts(self, project_dir):
        with open(".gitignore", "w") as f:
            f.write("*.pyc\n")
        assert check_gitignore_warning() is False

    def test_no_gitignore(self, project_dir):
        assert check_gitignore_warning() is False
