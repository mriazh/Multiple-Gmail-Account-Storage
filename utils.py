"""Utility functions for Gmail Account Manager."""

import json
import os
import tempfile


def atomic_write_text(filepath: str, content: str, encoding: str = "utf-8") -> None:
    """
    Atomically write text content to a file.

    Uses write-to-temp + os.replace() pattern to prevent partial writes.
    If the process crashes mid-write, the original file remains intact.

    Args:
        filepath: Target file path
        content: Text content to write
        encoding: File encoding (default: utf-8)
    """
    dir_path = os.path.dirname(filepath) or "."
    os.makedirs(dir_path, exist_ok=True)

    # Write to temp file in same directory (required for atomic os.replace)
    fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(temp_path, filepath)
    except BaseException:
        # Clean up temp file on any error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def atomic_write_bytes(filepath: str, data: bytes) -> None:
    """
    Atomically write binary content to a file.

    Uses write-to-temp + os.replace() pattern to prevent partial writes.
    If the process crashes mid-write, the original file remains intact.

    Args:
        filepath: Target file path
        data: Binary content to write
    """
    dir_path = os.path.dirname(filepath) or "."
    os.makedirs(dir_path, exist_ok=True)

    # Write to temp file in same directory (required for atomic os.replace)
    fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(temp_path, filepath)
    except BaseException:
        # Clean up temp file on any error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def atomic_write_json(filepath: str, data: dict, indent: int = 2) -> None:
    """
    Atomically write a JSON-serializable dict to a file.

    Args:
        filepath: Target file path
        data: Dictionary to serialize as JSON
        indent: JSON indentation (default: 2)
    """
    content = json.dumps(data, indent=indent, ensure_ascii=False)
    atomic_write_text(filepath, content)
