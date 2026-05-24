"""Signal handlers and graceful shutdown for Gmail Account Manager."""

import atexit
import logging
import signal
import sys

from crypto.temp_manager import cleanup_all_temp_dirs, get_open_temp_dirs

logger = logging.getLogger(__name__)

# Global Fernet key reference (set during startup)
_fernet_key: bytes | None = None

# Track if cleanup has already run
_cleanup_done = False


def setup_signal_handlers(fernet_key: bytes) -> None:
    """
    Register signal handlers and atexit for graceful shutdown.

    Args:
        fernet_key: Fernet key for re-encrypting open profiles
    """
    global _fernet_key
    _fernet_key = fernet_key

    # Register atexit handler
    atexit.register(_cleanup_on_exit)

    # Register signal handlers
    signal.signal(signal.SIGINT, _signal_handler)

    # Windows-specific: SIGBREAK (Ctrl+Break)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _signal_handler)


def _signal_handler(signum, frame):
    """Handle SIGINT/SIGBREAK for graceful shutdown."""
    logger.info(f"Received signal {signum}, performing cleanup...")
    print("\n" + "[!] Interrupted. Cleaning up...")
    _cleanup_on_exit()
    sys.exit(1)


def _cleanup_on_exit():
    """
    Cleanup handler: re-encrypt open profiles and remove temp dirs.

    Called by atexit and signal handlers. Idempotent (runs only once).
    """
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True

    open_dirs = get_open_temp_dirs()
    if not open_dirs:
        return

    logger.info(f"Cleanup: {len(open_dirs)} open temp dir(s) to process")

    # Re-encrypt any open profiles
    if _fernet_key:
        reencrypt_open_profiles(_fernet_key)

    # Clean up all temp directories
    cleanup_all_temp_dirs()


def reencrypt_open_profiles(fernet_key: bytes) -> None:
    """
    Re-encrypt all currently open (decrypted) profiles.

    Iterates through the global registry of open temp dirs and
    encrypts each one back to its .enc archive.
    """
    from crypto.profile_encryptor import encrypt_profile
    from crypto.integrity import update_checksum

    open_dirs = get_open_temp_dirs()

    for temp_dir in list(open_dirs):
        # Extract group name from temp dir name (format: gam_{group}_XXXXXXXX)
        group_name = _extract_group_from_temp(temp_dir)
        if group_name:
            try:
                logger.info(f"Re-encrypting profile: {group_name}")
                encrypt_profile(temp_dir, group_name, fernet_key)
                update_checksum(group_name)
            except Exception as e:
                logger.error(f"Failed to re-encrypt {group_name}: {e}")


def _extract_group_from_temp(temp_dir: str) -> str | None:
    """
    Extract group name from temp directory path.

    Temp dirs are named: gam_{group}_{random}
    """
    import os
    dirname = os.path.basename(temp_dir)

    if not dirname.startswith("gam_"):
        return None

    # Remove "gam_" prefix
    rest = dirname[4:]

    # Find the last underscore (before random suffix)
    # The random suffix is added by tempfile.mkdtemp
    parts = rest.rsplit("_", 1)
    if len(parts) >= 1:
        return parts[0] if parts[0] else None

    return None
