"""Profile directory encryption/decryption."""

import io
import os
import shutil
import tarfile
import tempfile

from cryptography.fernet import Fernet

from utils import atomic_write_bytes

# Prefix for temp directories (used for orphan detection)
TEMP_PREFIX = "gam_"


def encrypt_profile(temp_dir: str, group_name: str, fernet_key: bytes) -> None:
    """
    Encrypt a profile directory to a .enc archive.

    Steps:
    1. Create tar.gz of the directory contents
    2. Fernet-encrypt the tar.gz bytes
    3. Write encrypted bytes to {group_name}.enc atomically
    4. Delete the temp directory

    Args:
        temp_dir: Path to the decrypted profile directory
        group_name: Name of the group (used for .enc filename)
        fernet_key: Fernet key for encryption
    """
    enc_path = f"{group_name}.enc"

    # Step 1: Create tar.gz in memory
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
        # Add all files in the directory
        for item in os.listdir(temp_dir):
            item_path = os.path.join(temp_dir, item)
            tar.add(item_path, arcname=item)

    tar_bytes = tar_buffer.getvalue()

    # Step 2: Fernet encrypt
    fernet = Fernet(fernet_key)
    encrypted_data = fernet.encrypt(tar_bytes)

    # Step 3: Write atomically
    atomic_write_bytes(enc_path, encrypted_data)

    # Step 4: Delete temp directory
    _safe_rmtree(temp_dir)


def decrypt_profile(group_name: str, fernet_key: bytes) -> str:
    """
    Decrypt a .enc archive to a temporary directory.

    Steps:
    1. Read the .enc file
    2. Fernet-decrypt to get tar.gz bytes
    3. Create temp directory
    4. Extract tar.gz to temp directory

    Args:
        group_name: Name of the group
        fernet_key: Fernet key for decryption

    Returns:
        Path to the temporary directory containing the decrypted profile

    Raises:
        FileNotFoundError: If .enc file doesn't exist
        cryptography.fernet.InvalidToken: If key is wrong or data corrupted
    """
    enc_path = f"{group_name}.enc"

    if not os.path.exists(enc_path):
        raise FileNotFoundError(f"Profile archive not found: {enc_path}")

    # Step 1: Read encrypted file
    with open(enc_path, "rb") as f:
        encrypted_data = f.read()

    # Step 2: Decrypt
    fernet = Fernet(fernet_key)
    tar_bytes = fernet.decrypt(encrypted_data)

    # Step 3: Create temp directory
    temp_dir = tempfile.mkdtemp(prefix=f"{TEMP_PREFIX}{group_name}_")

    # Step 4: Extract tar.gz
    tar_buffer = io.BytesIO(tar_bytes)
    with tarfile.open(fileobj=tar_buffer, mode="r:gz") as tar:
        tar.extractall(path=temp_dir)

    return temp_dir


def create_backup(group_name: str) -> None:
    """
    Create a backup of the .enc archive before decryption.

    Copies {group_name}.enc → {group_name}.enc.bak
    Overwrites previous backup.
    """
    enc_path = f"{group_name}.enc"
    bak_path = f"{group_name}.enc.bak"

    if os.path.exists(enc_path):
        shutil.copy2(enc_path, bak_path)


def restore_backup(group_name: str) -> bool:
    """
    Restore .enc from .enc.bak backup.

    Returns True if backup existed and was restored, False otherwise.
    """
    enc_path = f"{group_name}.enc"
    bak_path = f"{group_name}.enc.bak"

    if os.path.exists(bak_path):
        shutil.copy2(bak_path, enc_path)
        return True
    return False


def profile_exists(group_name: str) -> bool:
    """Check if an encrypted profile archive exists for a group."""
    return os.path.exists(f"{group_name}.enc")


def scan_orphaned_temps() -> list[str]:
    """
    Find orphaned temp directories from previous crashes.

    Scans the system temp directory for directories matching our prefix pattern.
    """
    temp_base = tempfile.gettempdir()
    orphans = []

    try:
        for item in os.listdir(temp_base):
            if item.startswith(TEMP_PREFIX):
                full_path = os.path.join(temp_base, item)
                if os.path.isdir(full_path):
                    orphans.append(full_path)
    except OSError:
        pass

    return orphans


def cleanup_temp(temp_dir: str) -> None:
    """Delete temp directory with error handling for locked files."""
    _safe_rmtree(temp_dir)


def _safe_rmtree(path: str) -> None:
    """Remove directory tree with error handler for permission issues."""
    def _on_error(func, path, exc_info):
        """Handle errors during rmtree (e.g., read-only files)."""
        import stat
        os.chmod(path, stat.S_IWRITE)
        func(path)

    if os.path.exists(path):
        shutil.rmtree(path, onerror=_on_error)
