"""Encrypted credential storage (accounts.json)."""

import base64
import json
import os

from cryptography.fernet import Fernet

from crypto.key_derivation import derive_fernet_key, generate_salt
from utils import atomic_write_json

ACCOUNTS_PATH = "accounts.json"


def load() -> dict:
    """Load accounts.json, return parsed dict. Returns empty dict if missing."""
    if not os.path.exists(ACCOUNTS_PATH):
        return {}
    try:
        with open(ACCOUNTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save(data: dict) -> None:
    """Atomic write accounts.json."""
    atomic_write_json(ACCOUNTS_PATH, data)


def get_groups() -> list[str]:
    """Get all group names from accounts.json."""
    data = load()
    return list(data.keys())


def get_emails(group: str) -> list[str]:
    """Get plain-text email list for a group (no decryption needed)."""
    data = load()
    accounts = data.get(group, [])
    return [acc["email"] for acc in accounts]


def get_group_count(group: str) -> int:
    """Get number of accounts in a group."""
    return len(get_emails(group))


def add(group: str, email: str, password: str, master_key: bytes) -> None:
    """
    Add encrypted credential to group.

    Args:
        group: Group name
        email: Gmail address (stored plain text)
        password: Account password (will be encrypted)
        master_key: Fernet key derived from master PIN/Password
    """
    data = load()

    if group not in data:
        data[group] = []

    # Check for duplicate
    existing_emails = [acc["email"].lower() for acc in data[group]]
    if email.lower() in existing_emails:
        raise ValueError(f"Email {email} already exists in {group}")

    # Check capacity
    if len(data[group]) >= 5:
        raise ValueError(f"Group {group} is full (5/5 accounts)")

    # Encrypt password with per-entry salt
    salt = generate_salt()
    # Use master_key directly (already a valid Fernet key)
    fernet = Fernet(master_key)
    encrypted_password = fernet.encrypt(password.encode("utf-8")).decode("utf-8")

    entry = {
        "email": email,
        "password": encrypted_password,
        "salt": base64.b64encode(salt).decode("utf-8"),
    }

    data[group].append(entry)
    save(data)


def remove(group: str, email: str) -> None:
    """Remove credential from group."""
    data = load()

    if group not in data:
        raise ValueError(f"Group {group} not found")

    original_count = len(data[group])
    data[group] = [acc for acc in data[group] if acc["email"].lower() != email.lower()]

    if len(data[group]) == original_count:
        raise ValueError(f"Email {email} not found in {group}")

    # Remove empty group key
    if not data[group]:
        del data[group]

    save(data)


def update_password(group: str, email: str, new_password: str, master_key: bytes) -> None:
    """Update encrypted password for existing account."""
    data = load()

    if group not in data:
        raise ValueError(f"Group {group} not found")

    for acc in data[group]:
        if acc["email"].lower() == email.lower():
            # Re-encrypt with new salt
            salt = generate_salt()
            fernet = Fernet(master_key)
            encrypted_password = fernet.encrypt(new_password.encode("utf-8")).decode("utf-8")

            acc["password"] = encrypted_password
            acc["salt"] = base64.b64encode(salt).decode("utf-8")
            save(data)
            return

    raise ValueError(f"Email {email} not found in {group}")


def decrypt_password(group: str, email: str, master_key: bytes) -> str:
    """Decrypt and return password for an account."""
    data = load()

    if group not in data:
        raise ValueError(f"Group {group} not found")

    for acc in data[group]:
        if acc["email"].lower() == email.lower():
            fernet = Fernet(master_key)
            return fernet.decrypt(acc["password"].encode("utf-8")).decode("utf-8")

    raise ValueError(f"Email {email} not found in {group}")


def email_exists(group: str, email: str) -> bool:
    """Check if email already exists in a group."""
    emails = get_emails(group)
    return email.lower() in [e.lower() for e in emails]


def check_gitignore_warning() -> bool:
    """
    Check if accounts.json is in .gitignore.
    Returns True if properly gitignored, False if warning needed.
    """
    gitignore_path = ".gitignore"
    if not os.path.exists(gitignore_path):
        return False

    with open(gitignore_path, "r", encoding="utf-8") as f:
        content = f.read()

    return "accounts.json" in content
