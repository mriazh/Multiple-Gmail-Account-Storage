"""Migration script: convert existing Group_*/ folders to .enc archives."""

import getpass
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crypto.key_derivation import derive_fernet_key, verify_credential
from crypto.profile_encryptor import encrypt_profile, profile_exists
from crypto.integrity import update_checksum
from auth.auth_config import load_auth_config, auth_config_exists

import base64


def main():
    """
    Migration entry point:
    1. Authenticate to derive Fernet key
    2. Find all Group_*/ directories
    3. For each: tar.gz → encrypt → write .enc → update checksums
    4. Prompt to delete originals after success
    """
    print("=== Gmail Account Manager — Migration Tool ===")
    print()

    # Authenticate first
    fernet_key = _authenticate()
    if fernet_key is None:
        print("Authentication failed. Cannot proceed with migration.")
        return

    # Find Group_* directories
    groups = _find_group_directories()
    if not groups:
        print("No Group_*/ directories found to migrate.")
        return

    print(f"\nFound {len(groups)} group(s) to migrate:")
    for g in groups:
        print(f"  • {g}")
    print()

    # Migrate each group
    migrated = []
    skipped = []

    for group_dir in groups:
        group_name = os.path.basename(group_dir)

        # Skip if already encrypted (idempotent)
        if profile_exists(group_name):
            print(f"  [SKIP] {group_name} — already has .enc archive")
            skipped.append(group_name)
            continue

        print(f"  [MIGRATING] {group_name}...")
        try:
            # encrypt_profile expects a temp dir path and will delete it
            # We don't want to delete the original yet, so we'll do it manually
            _encrypt_directory(group_dir, group_name, fernet_key)
            update_checksum(group_name)
            migrated.append(group_name)
            print(f"  [OK] {group_name} → {group_name}.enc")
        except Exception as e:
            print(f"  [ERROR] {group_name}: {e}")

    # Summary
    print(f"\n--- Migration Summary ---")
    print(f"  Migrated: {len(migrated)}")
    print(f"  Skipped:  {len(skipped)}")
    print()

    # Prompt to delete originals
    if migrated:
        print("Delete original Group_*/ directories? (They are now encrypted)")
        confirm = input("(y/n): ").strip().lower()
        if confirm == "y":
            for group_name in migrated:
                group_dir = group_name  # relative path
                if os.path.isdir(group_dir):
                    import shutil
                    shutil.rmtree(group_dir)
                    print(f"  Deleted: {group_dir}/")
            print("Done.")
        else:
            print("Originals kept. You can delete them manually later.")


def _authenticate() -> bytes | None:
    """Authenticate user and return Fernet key."""
    if not auth_config_exists():
        print("No auth config found. Please run the main application first.")
        return None

    config = load_auth_config()
    if config is None:
        return None

    credential_type = config.get("credential_type", "pin")
    prompt = "Enter PIN: " if credential_type == "pin" else "Enter Password: "

    for attempt in range(3):
        credential = getpass.getpass(prompt)
        if verify_credential(credential, config["credential_hash"]):
            salt = base64.b64decode(config["credential_salt"])
            return derive_fernet_key(credential, salt)
        print(f"Incorrect. {2 - attempt} attempts remaining.")

    return None


def _find_group_directories() -> list[str]:
    """Find all Group_*/ directories in the project root."""
    groups = []
    for item in os.listdir("."):
        if os.path.isdir(item) and re.match(r'^Group_\d+$', item):
            groups.append(item)
    return sorted(groups)


def _encrypt_directory(source_dir: str, group_name: str, fernet_key: bytes) -> None:
    """
    Encrypt a directory to .enc without deleting the source.

    This is a modified version of encrypt_profile that doesn't delete the source.
    """
    import io
    import tarfile
    from cryptography.fernet import Fernet
    from utils import atomic_write_bytes

    enc_path = f"{group_name}.enc"

    # Create tar.gz in memory
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
        for item in os.listdir(source_dir):
            item_path = os.path.join(source_dir, item)
            tar.add(item_path, arcname=item)

    tar_bytes = tar_buffer.getvalue()

    # Fernet encrypt
    fernet = Fernet(fernet_key)
    encrypted_data = fernet.encrypt(tar_bytes)

    # Write atomically
    atomic_write_bytes(enc_path, encrypted_data)


if __name__ == "__main__":
    main()
