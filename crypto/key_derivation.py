"""Argon2id KDF and Fernet key management."""

import base64
import hashlib
import hmac
import os
import winreg

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from argon2.low_level import Type as Argon2Type
from cryptography.fernet import Fernet

# Argon2id parameters (as specified in requirements)
ARGON2_TIME_COST = 2
ARGON2_MEMORY_COST = 65536  # 64MB
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN = 32  # 32 bytes for Fernet key
ARGON2_SALT_LEN = 16  # 16 bytes

# Application secret for SMTP key derivation (machine-bound)
_APP_SECRET = "gmail-account-manager-smtp-v1"

# Configure Argon2id hasher for credential hashing
_hasher = PasswordHasher(
    time_cost=ARGON2_TIME_COST,
    memory_cost=ARGON2_MEMORY_COST,
    parallelism=ARGON2_PARALLELISM,
    hash_len=ARGON2_HASH_LEN,
    salt_len=ARGON2_SALT_LEN,
    type=Argon2Type.ID,  # argon2id
)


def generate_salt() -> bytes:
    """Generate a random 16-byte salt."""
    return os.urandom(16)


def derive_fernet_key(password: str, salt: bytes) -> bytes:
    """
    Derive a Fernet-compatible key from password + salt using Argon2id.

    Returns a 44-character base64url-encoded key suitable for Fernet.
    """
    # Use argon2 low-level to get raw hash bytes
    from argon2.low_level import hash_secret_raw, Type

    raw_key = hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM,
        hash_len=32,
        type=Type.ID,
    )
    # Fernet requires a 32-byte key, base64url-encoded (44 chars)
    return base64.urlsafe_b64encode(raw_key)


def hash_credential(credential: str) -> str:
    """
    Hash a credential (PIN/password/recovery key) with Argon2id.

    Returns the full Argon2id hash string (includes salt, params, hash).
    """
    return _hasher.hash(credential)


def verify_credential(credential: str, stored_hash: str) -> bool:
    """
    Verify a credential against its Argon2id hash.

    Returns True if match, False otherwise.
    """
    try:
        return _hasher.verify(stored_hash, credential)
    except VerifyMismatchError:
        return False


def derive_smtp_key() -> bytes:
    """
    Derive machine-bound Fernet key from Windows MachineGuid.

    Uses HMAC-SHA256(MachineGuid, app_secret) to create a deterministic
    key that only works on this specific machine.

    Returns a 44-character base64url-encoded Fernet key.
    """
    machine_guid = _get_machine_guid()

    # HMAC-SHA256 to derive 32-byte key
    raw_key = hmac.new(
        _APP_SECRET.encode("utf-8"),
        machine_guid.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    return base64.urlsafe_b64encode(raw_key)


def _get_machine_guid() -> str:
    """
    Retrieve Windows Machine GUID from registry.

    Location: HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid
    """
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        )
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return guid
    except (OSError, WindowsError) as e:
        raise RuntimeError(
            "Cannot retrieve Windows MachineGuid. "
            "This application requires Windows."
        ) from e


def create_fernet(key: bytes) -> Fernet:
    """Create a Fernet instance from a derived key."""
    return Fernet(key)
