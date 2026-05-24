"""Secure temp directory management with Windows ACL."""

import logging
import os
import shutil
import stat
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# Prefix for temp directories (used for orphan detection)
TEMP_PREFIX = "gam_"

# Global registry of open temp dirs (for signal handler cleanup)
_open_temp_dirs: list[str] = []


def create_secure_temp(group_name: str) -> str:
    """
    Create a secure temp directory with Windows ACL (user-only access).

    Uses icacls to restrict access to the current user only.

    Args:
        group_name: Group name for the prefix

    Returns:
        Path to the created temp directory
    """
    temp_dir = tempfile.mkdtemp(prefix=f"{TEMP_PREFIX}{group_name}_")
    _apply_windows_acl(temp_dir)
    register_temp_dir(temp_dir)
    logger.info(f"Created secure temp dir: {temp_dir}")
    return temp_dir


def _apply_windows_acl(path: str) -> None:
    """
    Apply Windows ACL to restrict directory to current user only.

    Uses icacls to:
    1. Remove inherited permissions
    2. Grant full control only to current user
    """
    try:
        username = os.environ.get("USERNAME", os.getlogin())

        # Remove inheritance and existing permissions
        subprocess.run(
            ["icacls", path, "/inheritance:r"],
            capture_output=True,
            timeout=10,
        )

        # Grant full control to current user only
        subprocess.run(
            ["icacls", path, "/grant:r", f"{username}:(OI)(CI)F"],
            capture_output=True,
            timeout=10,
        )

        logger.debug(f"Applied ACL to {path} for user {username}")
    except Exception as e:
        # Non-fatal: ACL is a security enhancement, not required
        logger.warning(f"Could not apply Windows ACL to {path}: {e}")


def register_temp_dir(temp_dir: str) -> None:
    """Register a temp dir for cleanup on exit."""
    if temp_dir not in _open_temp_dirs:
        _open_temp_dirs.append(temp_dir)


def unregister_temp_dir(temp_dir: str) -> None:
    """Remove a temp dir from the registry (after successful cleanup)."""
    if temp_dir in _open_temp_dirs:
        _open_temp_dirs.remove(temp_dir)


def get_open_temp_dirs() -> list[str]:
    """Get list of currently registered (open) temp directories."""
    return list(_open_temp_dirs)


def cleanup_temp(temp_dir: str) -> None:
    """
    Delete temp directory with error handling for locked files.

    Uses onerror handler to deal with read-only or locked files.
    """
    if not os.path.exists(temp_dir):
        unregister_temp_dir(temp_dir)
        return

    def _on_error(func, path, exc_info):
        """Handle errors during rmtree (e.g., read-only files on Windows)."""
        try:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            func(path)
        except Exception as e:
            logger.warning(f"Could not remove {path}: {e}")

    try:
        shutil.rmtree(temp_dir, onerror=_on_error)
        logger.info(f"Cleaned up temp dir: {temp_dir}")
    except Exception as e:
        logger.error(f"Failed to cleanup {temp_dir}: {e}")

    unregister_temp_dir(temp_dir)


def cleanup_all_temp_dirs() -> None:
    """Clean up all registered temp directories."""
    for temp_dir in list(_open_temp_dirs):
        cleanup_temp(temp_dir)


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


def prompt_orphan_cleanup() -> None:
    """Scan for orphaned temps and prompt user to clean up."""
    from i18n import t

    orphans = scan_orphaned_temps()
    if not orphans:
        return

    for orphan in orphans:
        print(t("profile.orphan_found", path=orphan))
        choice = input(t("profile.orphan_cleanup")).strip().lower()
        if choice == "y":
            cleanup_temp(orphan)
