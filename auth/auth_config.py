"""Auth configuration management (auth_config.json)."""

import json
import os
from datetime import datetime

from utils import atomic_write_json

AUTH_CONFIG_PATH = os.path.join("config", "auth_config.json")

DEFAULT_LOCKOUT = {
    "failed_attempts": 0,
    "last_failed": None,
    "lockout_until": None,
    "backoff_level": 0,
}


def auth_config_exists() -> bool:
    """Check if auth_config.json exists."""
    return os.path.exists(AUTH_CONFIG_PATH)


def load_auth_config() -> dict | None:
    """
    Load auth_config.json.
    Returns None if file doesn't exist.
    """
    if not auth_config_exists():
        return None
    try:
        with open(AUTH_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure lockout object exists with all fields
        if "lockout" not in data:
            data["lockout"] = DEFAULT_LOCKOUT.copy()
        else:
            for key, val in DEFAULT_LOCKOUT.items():
                if key not in data["lockout"]:
                    data["lockout"][key] = val
        return data
    except (json.JSONDecodeError, OSError):
        return None


def save_auth_config(config: dict) -> None:
    """Save auth_config.json atomically."""
    os.makedirs("config", exist_ok=True)
    atomic_write_json(AUTH_CONFIG_PATH, config)


def create_auth_config(
    credential_type: str,
    credential_hash: str,
    credential_salt: str,
    recovery_email_hash: str,
    recovery_key_hash: str,
    hint: str,
) -> dict:
    """
    Create a new auth config dict with all required fields.
    
    Args:
        credential_type: "pin" or "password"
        credential_hash: Argon2id hash of the credential
        credential_salt: Base64-encoded salt used for Fernet key derivation
        recovery_email_hash: Argon2id hash of recovery email
        recovery_key_hash: Argon2id hash of recovery key
        hint: Plain text hint for the credential
        
    Returns:
        Complete auth config dict ready to save
    """
    return {
        "version": "1.0",
        "credential_type": credential_type,
        "credential_hash": credential_hash,
        "credential_salt": credential_salt,
        "recovery_email_hash": recovery_email_hash,
        "recovery_key_hash": recovery_key_hash,
        "hint": hint,
        "lockout": DEFAULT_LOCKOUT.copy(),
        "created_at": datetime.now().isoformat(),
    }


def update_lockout(failed_attempts: int, backoff_level: int, lockout_until: str | None = None) -> None:
    """Update lockout state in auth_config."""
    config = load_auth_config()
    if config is None:
        return
    
    config["lockout"]["failed_attempts"] = failed_attempts
    config["lockout"]["last_failed"] = datetime.now().isoformat()
    config["lockout"]["backoff_level"] = backoff_level
    config["lockout"]["lockout_until"] = lockout_until
    save_auth_config(config)


def reset_lockout() -> None:
    """Reset lockout state (after successful login or 24h reset)."""
    config = load_auth_config()
    if config is None:
        return
    
    config["lockout"] = DEFAULT_LOCKOUT.copy()
    save_auth_config(config)


def update_credential(credential_hash: str, credential_salt: str, credential_type: str | None = None, hint: str | None = None) -> None:
    """Update credential after password reset."""
    config = load_auth_config()
    if config is None:
        return
    
    config["credential_hash"] = credential_hash
    config["credential_salt"] = credential_salt
    if credential_type:
        config["credential_type"] = credential_type
    if hint:
        config["hint"] = hint
    
    # Reset lockout on credential change
    config["lockout"] = DEFAULT_LOCKOUT.copy()
    save_auth_config(config)


def delete_auth_config() -> None:
    """Delete auth_config.json (used by nuke operation)."""
    if os.path.exists(AUTH_CONFIG_PATH):
        os.remove(AUTH_CONFIG_PATH)
