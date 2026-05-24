"""Tests for crypto module — key derivation, encryption, integrity."""

import base64
import os

import pytest
from cryptography.fernet import Fernet, InvalidToken

from crypto.key_derivation import (
    generate_salt,
    derive_fernet_key,
    hash_credential,
    verify_credential,
)
from crypto.profile_encryptor import (
    encrypt_profile,
    decrypt_profile,
    create_backup,
    restore_backup,
    profile_exists,
    cleanup_temp,
)
from crypto.integrity import (
    verify_checksum,
    update_checksum,
    remove_checksum,
    get_checksum,
)


class TestKeyDerivation:
    def test_generate_salt_length(self):
        salt = generate_salt()
        assert len(salt) == 16

    def test_generate_salt_random(self):
        s1 = generate_salt()
        s2 = generate_salt()
        assert s1 != s2

    def test_derive_fernet_key_valid(self):
        salt = generate_salt()
        key = derive_fernet_key("mypassword", salt)
        # Should be valid base64url, 44 chars
        assert len(key) == 44
        # Should be usable as Fernet key
        f = Fernet(key)
        token = f.encrypt(b"test")
        assert f.decrypt(token) == b"test"

    def test_derive_fernet_key_deterministic(self):
        salt = generate_salt()
        k1 = derive_fernet_key("password123", salt)
        k2 = derive_fernet_key("password123", salt)
        assert k1 == k2

    def test_derive_fernet_key_different_passwords(self):
        salt = generate_salt()
        k1 = derive_fernet_key("password1", salt)
        k2 = derive_fernet_key("password2", salt)
        assert k1 != k2

    def test_derive_fernet_key_different_salts(self):
        s1 = generate_salt()
        s2 = generate_salt()
        k1 = derive_fernet_key("same_password", s1)
        k2 = derive_fernet_key("same_password", s2)
        assert k1 != k2

    def test_hash_credential(self):
        h = hash_credential("my_pin_1234")
        assert h.startswith("$argon2id$")
        assert len(h) > 50

    def test_verify_credential_correct(self):
        h = hash_credential("secret123")
        assert verify_credential("secret123", h) is True

    def test_verify_credential_wrong(self):
        h = hash_credential("secret123")
        assert verify_credential("wrong", h) is False

    def test_verify_credential_empty(self):
        h = hash_credential("notempty")
        assert verify_credential("", h) is False

    def test_hash_different_inputs(self):
        h1 = hash_credential("input1")
        h2 = hash_credential("input2")
        assert h1 != h2

    def test_hash_same_input_different_hashes(self):
        """Argon2 uses random salt, so same input → different hash strings."""
        h1 = hash_credential("same")
        h2 = hash_credential("same")
        assert h1 != h2  # Different salts
        # But both verify
        assert verify_credential("same", h1) is True
        assert verify_credential("same", h2) is True


class TestProfileEncryptor:
    def _make_test_profile(self, path):
        """Create a fake profile directory with some files."""
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "prefs.js"), "w") as f:
            f.write("user_pref('test', true);")
        with open(os.path.join(path, "cookies.sqlite"), "wb") as f:
            f.write(os.urandom(256))
        sub = os.path.join(path, "subdir")
        os.makedirs(sub, exist_ok=True)
        with open(os.path.join(sub, "nested.txt"), "w") as f:
            f.write("nested content")

    def test_encrypt_decrypt_roundtrip(self, project_dir):
        # Create a profile
        profile_path = str(project_dir / "test_profile")
        self._make_test_profile(profile_path)

        # Generate key
        salt = generate_salt()
        key = derive_fernet_key("testpass", salt)

        # Encrypt
        encrypt_profile(profile_path, "TestGroup", key)
        assert os.path.exists("TestGroup.enc")
        assert not os.path.exists(profile_path)  # Source deleted

        # Decrypt
        temp_dir = decrypt_profile("TestGroup", key)
        assert os.path.isdir(temp_dir)
        assert os.path.exists(os.path.join(temp_dir, "prefs.js"))
        assert os.path.exists(os.path.join(temp_dir, "cookies.sqlite"))
        assert os.path.exists(os.path.join(temp_dir, "subdir", "nested.txt"))

        # Verify content
        with open(os.path.join(temp_dir, "prefs.js"), "r") as f:
            assert f.read() == "user_pref('test', true);"

        cleanup_temp(temp_dir)

    def test_decrypt_wrong_key(self, project_dir):
        profile_path = str(project_dir / "test_profile")
        self._make_test_profile(profile_path)

        salt = generate_salt()
        key1 = derive_fernet_key("correct", salt)
        key2 = derive_fernet_key("wrong", generate_salt())

        encrypt_profile(profile_path, "WrongKey", key1)

        with pytest.raises(InvalidToken):
            decrypt_profile("WrongKey", key2)

    def test_decrypt_missing_file(self, project_dir):
        salt = generate_salt()
        key = derive_fernet_key("test", salt)

        with pytest.raises(FileNotFoundError):
            decrypt_profile("NonExistent", key)

    def test_backup_restore(self, project_dir):
        profile_path = str(project_dir / "test_profile")
        self._make_test_profile(profile_path)

        salt = generate_salt()
        key = derive_fernet_key("test", salt)

        encrypt_profile(profile_path, "BackupTest", key)
        original_size = os.path.getsize("BackupTest.enc")

        # Create backup
        create_backup("BackupTest")
        assert os.path.exists("BackupTest.enc.bak")

        # Corrupt the .enc
        with open("BackupTest.enc", "wb") as f:
            f.write(b"corrupted")

        # Restore
        assert restore_backup("BackupTest") is True
        assert os.path.getsize("BackupTest.enc") == original_size

    def test_restore_no_backup(self, project_dir):
        assert restore_backup("NoBackup") is False

    def test_profile_exists(self, project_dir):
        assert profile_exists("Nope") is False
        with open("Exists.enc", "wb") as f:
            f.write(b"data")
        assert profile_exists("Exists") is True


class TestIntegrity:
    def test_verify_no_checksum_stored(self, project_dir):
        """First time — no stored checksum → returns True."""
        with open("NewGroup.enc", "wb") as f:
            f.write(b"some data")
        assert verify_checksum("NewGroup") is True

    def test_update_and_verify(self, project_dir):
        with open("Group_1.enc", "wb") as f:
            f.write(b"original content")

        update_checksum("Group_1")
        assert verify_checksum("Group_1") is True

    def test_verify_after_modification(self, project_dir):
        with open("Group_2.enc", "wb") as f:
            f.write(b"original")

        update_checksum("Group_2")

        # Modify the file
        with open("Group_2.enc", "wb") as f:
            f.write(b"tampered")

        assert verify_checksum("Group_2") is False

    def test_verify_missing_file(self, project_dir):
        assert verify_checksum("Missing") is False

    def test_remove_checksum(self, project_dir):
        with open("ToRemove.enc", "wb") as f:
            f.write(b"data")
        update_checksum("ToRemove")
        assert get_checksum("ToRemove") is not None

        remove_checksum("ToRemove")
        assert get_checksum("ToRemove") is None

    def test_get_checksum_not_stored(self, project_dir):
        assert get_checksum("NeverStored") is None
