"""SHA256 checksum verification for profile archives."""

import hashlib
import json
import os

from utils import atomic_write_json

CHECKSUMS_PATH = "checksums.json"

DEFAULT_CHECKSUMS = {
    "version": "1.0",
    "checksums": {},
}


def _load_checksums() -> dict:
    """Load checksums.json, create with defaults if missing."""
    if not os.path.exists(CHECKSUMS_PATH):
        return DEFAULT_CHECKSUMS.copy()
    try:
        with open(CHECKSUMS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "checksums" not in data:
            data["checksums"] = {}
        if "version" not in data:
            data["version"] = "1.0"
        return data
    except (json.JSONDecodeError, OSError):
        return DEFAULT_CHECKSUMS.copy()


def _save_checksums(data: dict) -> None:
    """Save checksums.json atomically."""
    atomic_write_json(CHECKSUMS_PATH, data)


def _compute_sha256(filepath: str) -> str:
    """Compute SHA256 hex digest of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_checksum(group_name: str) -> bool:
    """
    Verify SHA256 of .enc file against stored checksum.

    Returns True if match (or no checksum stored yet), False if mismatch.
    """
    enc_path = f"{group_name}.enc"

    if not os.path.exists(enc_path):
        return False

    data = _load_checksums()
    stored_hash = data["checksums"].get(group_name)

    # No stored checksum yet — treat as valid (first time)
    if stored_hash is None:
        return True

    actual_hash = _compute_sha256(enc_path)
    return actual_hash == stored_hash


def update_checksum(group_name: str) -> None:
    """
    Compute SHA256 of .enc file and update checksums.json.
    """
    enc_path = f"{group_name}.enc"

    if not os.path.exists(enc_path):
        return

    data = _load_checksums()
    data["checksums"][group_name] = _compute_sha256(enc_path)
    _save_checksums(data)


def remove_checksum(group_name: str) -> None:
    """Remove a group's checksum entry (when group is deleted)."""
    data = _load_checksums()
    if group_name in data["checksums"]:
        del data["checksums"][group_name]
        _save_checksums(data)


def get_checksum(group_name: str) -> str | None:
    """Get stored checksum for a group, or None if not stored."""
    data = _load_checksums()
    return data["checksums"].get(group_name)
