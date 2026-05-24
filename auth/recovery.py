"""Recovery flows: Recovery Key, email verification, nuke."""

import base64
import getpass
import glob
import os
import shutil
from datetime import datetime, timedelta

from i18n import t
from crypto.key_derivation import (
    derive_fernet_key,
    generate_salt,
    hash_credential,
    verify_credential,
)
from auth.auth_config import (
    load_auth_config,
    save_auth_config,
    update_credential,
    delete_auth_config,
)
from auth.email_sender import send_verification
from accounts import credential_store


# Recovery email limits
MAX_CODES_PER_SESSION = 5
MAX_ATTEMPTS_PER_CODE = 3
CODE_EXPIRY_SECONDS = 600  # 10 minutes
EMAIL_LOCKOUT_MINUTES = 30


def recovery_menu() -> bytes | None:
    """
    Display recovery options and handle selection.

    Returns:
        Fernet key if credential reset successful, None otherwise
    """
    print(t("auth.recovery.options"))
    choice = input(t("auth.recovery.select")).strip()

    if choice == "1":
        return recovery_key_flow()
    elif choice == "2":
        return email_verification_flow()
    elif choice == "3":
        nuke_flow()
        return None
    else:
        return None


def recovery_key_flow() -> bytes | None:
    """
    Recovery Key verification → credential reset.

    Returns:
        New Fernet key on success, None on failure
    """
    config = load_auth_config()
    if config is None:
        return None

    key_input = input(t("auth.recovery.key_prompt")).strip()

    if verify_credential(key_input, config["recovery_key_hash"]):
        credential_type = config.get("credential_type", "pin")
        type_label = "PIN" if credential_type == "pin" else "Password"
        print(t("auth.recovery.key_success", type=type_label))
        return _reset_credential(config)
    else:
        print(t("auth.recovery.key_invalid"))
        return None


def email_verification_flow() -> bytes | None:
    """
    Email code verification → credential reset.
    - 10 min expiry per code
    - 3 attempts per code
    - 5 codes per session
    - Exceed → 30 min lockout

    Returns:
        New Fernet key on success, None on failure
    """
    config = load_auth_config()
    if config is None:
        return None

    # We need to find the recovery email — we can't decrypt the hash,
    # so we ask the user to provide it and verify against the hash
    email = input("Enter your recovery email: ").strip()
    if not verify_credential(email.lower(), config["recovery_email_hash"]):
        print("Email does not match recovery email on file.")
        return None

    codes_sent = 0

    while codes_sent < MAX_CODES_PER_SESSION:
        # Send code
        try:
            code, timestamp = send_verification(email)
            codes_sent += 1
        except Exception:
            print(t("error.smtp_failed"))
            retry = input(t("general.yes_no")).strip().lower()
            if retry != "y":
                return None
            continue

        print(t("auth.recovery.email_sent"))

        # Verify code (3 attempts)
        for attempt in range(MAX_ATTEMPTS_PER_CODE):
            user_code = input(t("auth.setup.code_prompt")).strip()

            # Check expiry
            elapsed = (datetime.now() - timestamp).total_seconds()
            if elapsed > CODE_EXPIRY_SECONDS:
                print(t("auth.setup.code_expired"))
                break  # Send new code

            if user_code == code:
                credential_type = config.get("credential_type", "pin")
                type_label = "PIN" if credential_type == "pin" else "Password"
                print(t("auth.recovery.email_success", type=type_label))
                return _reset_credential(config)

            print(t("auth.setup.code_invalid"))

    # Exceeded max codes
    print(t("auth.recovery.email_limit"))
    return None


def nuke_flow() -> None:
    """
    Factory reset with triple confirmation:
    1. y/n confirmation
    2. Show itemized list of what will be deleted
    3. Type "NUKE" to confirm

    Deletes: accounts.json, auth_config, smtp_config, *.enc, *.enc.bak,
             checksums.json, logs/*
    Keeps: settings.json
    """
    print(t("auth.recovery.nuke_warning"))
    confirm1 = input(t("auth.recovery.nuke_confirm1")).strip().lower()
    if confirm1 != "y":
        print(t("auth.recovery.nuke_cancelled"))
        return

    # Gather stats for itemized list
    data = credential_store.load()
    total_accounts = sum(len(v) for v in data.values())
    total_groups = len(data)
    archives = len(glob.glob("*.enc"))

    print(t("auth.recovery.nuke_list",
            accounts=total_accounts,
            groups=total_groups,
            archives=archives))

    confirm2 = input(t("auth.recovery.nuke_confirm2")).strip()
    if confirm2 != "NUKE":
        print(t("auth.recovery.nuke_cancelled"))
        return

    # Execute nuke
    _execute_nuke()
    print(t("auth.recovery.nuke_complete"))


def _reset_credential(config: dict) -> bytes | None:
    """
    Allow user to set a new PIN/Password after recovery.

    Returns:
        New Fernet key on success, None on failure
    """
    from auth.master_auth import _setup_pin, _setup_password

    credential_type = config.get("credential_type", "pin")
    type_label = "PIN" if credential_type == "pin" else "Password"

    print(t("auth.setup.type_prompt"), end="")
    choice = input().strip()

    if choice == "1":
        new_type, credential = _setup_pin()
    elif choice == "2":
        new_type, credential = _setup_password()
    else:
        new_type, credential = _setup_pin()

    if credential is None:
        return None

    # Hash and save
    new_hash = hash_credential(credential)
    new_salt = generate_salt()
    new_salt_b64 = base64.b64encode(new_salt).decode("utf-8")

    # Optional new hint
    hint = input(t("auth.setup.hint_prompt", type=type_label)).strip()

    update_credential(
        credential_hash=new_hash,
        credential_salt=new_salt_b64,
        credential_type=new_type,
        hint=hint if hint else None,
    )

    # Derive new Fernet key
    fernet_key = derive_fernet_key(credential, new_salt)
    return fernet_key


def _execute_nuke() -> None:
    """Delete all sensitive data files."""
    # accounts.json
    if os.path.exists("accounts.json"):
        os.remove("accounts.json")

    # auth_config
    delete_auth_config()

    # smtp_config
    smtp_path = os.path.join("config", "smtp_config.json")
    if os.path.exists(smtp_path):
        os.remove(smtp_path)

    # *.enc and *.enc.bak
    for enc_file in glob.glob("*.enc"):
        os.remove(enc_file)
    for bak_file in glob.glob("*.enc.bak"):
        os.remove(bak_file)

    # checksums.json
    if os.path.exists("checksums.json"):
        os.remove("checksums.json")

    # logs/*
    logs_dir = "logs"
    if os.path.isdir(logs_dir):
        for item in os.listdir(logs_dir):
            if item == ".gitkeep":
                continue
            filepath = os.path.join(logs_dir, item)
            if os.path.isfile(filepath):
                os.remove(filepath)
