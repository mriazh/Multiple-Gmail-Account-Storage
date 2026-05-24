"""Group CRUD, naming, validation."""

import os
import re

from accounts import credential_store

# Reserved Windows filenames that cannot be used as group names
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def list_groups() -> list[dict]:
    """
    List all groups with their account counts.

    Returns list of dicts: [{"name": "Group_1", "count": 3}, ...]
    """
    groups = credential_store.get_groups()
    result = []
    for group in sorted(groups):
        count = credential_store.get_group_count(group)
        result.append({"name": group, "count": count})
    return result


def get_all_group_names() -> list[str]:
    """Get all group names (from accounts.json + .enc files on disk)."""
    # From credential store
    json_groups = set(credential_store.get_groups())

    # From .enc files on disk
    enc_groups = set()
    for item in os.listdir("."):
        if item.endswith(".enc") and not item.endswith(".enc.bak"):
            enc_groups.add(item[:-4])  # Remove .enc extension

    return sorted(json_groups | enc_groups)


def create_group(name: str | None = None) -> str:
    """
    Create a new group.

    Args:
        name: Custom group name, or None for auto-increment (Group_N+1)

    Returns:
        The created group name

    Raises:
        ValueError: If name is invalid or already exists
    """
    if name is None:
        name = _auto_increment_name()
    else:
        valid, error = validate_name(name)
        if not valid:
            raise ValueError(error)

    # Ensure group entry exists in accounts.json
    data = credential_store.load()
    if name not in data:
        data[name] = []
        credential_store.save(data)

    return name


def validate_name(name: str) -> tuple[bool, str]:
    """
    Validate a group name.

    Checks:
    - Only alphanumeric, underscore, dash
    - No path traversal (../, .\\, /, \\)
    - Not a reserved Windows filename
    - Not already existing (case-insensitive)
    - Not empty, not too long (max 50 chars)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Group name cannot be empty."

    if len(name) > 50:
        return False, "Group name too long (max 50 characters)."

    # Check allowed characters
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        return False, "Group name can only contain letters, numbers, underscores, and dashes."

    # Check path traversal
    if '..' in name or '/' in name or '\\' in name:
        return False, "Group name contains invalid path characters."

    # Check starts with dot or dash
    if name.startswith(('.', '-')):
        return False, "Group name cannot start with '.' or '-'."

    # Check reserved Windows names
    if name.upper() in WINDOWS_RESERVED:
        return False, f"'{name}' is a reserved Windows filename."

    # Check duplicate (case-insensitive)
    existing = get_all_group_names()
    if name.lower() in [g.lower() for g in existing]:
        return False, f"Group '{name}' already exists."

    return True, ""


def get_group_count(group: str) -> int:
    """Get number of accounts in a group."""
    return credential_store.get_group_count(group)


def group_exists(name: str) -> bool:
    """Check if a group exists (case-insensitive)."""
    existing = get_all_group_names()
    return name.lower() in [g.lower() for g in existing]


def resolve_group_input(user_input: str) -> str | None:
    """
    Resolve user input to an actual group name.

    Accepts:
    - A number (index into sorted group list, 1-based)
    - A group name (case-insensitive match)

    Returns:
        Resolved group name, or None if not found
    """
    groups = get_all_group_names()

    # Try as number
    if user_input.isdigit():
        idx = int(user_input) - 1
        if 0 <= idx < len(groups):
            return groups[idx]
        return None

    # Try case-insensitive match
    for group in groups:
        if group.lower() == user_input.lower():
            return group

    return None


def _auto_increment_name() -> str:
    """Generate next Group_N name by finding highest existing number."""
    existing = get_all_group_names()
    max_num = 0

    for name in existing:
        match = re.match(r'^Group_(\d+)$', name)
        if match:
            num = int(match.group(1))
            max_num = max(max_num, num)

    return f"Group_{max_num + 1}"
