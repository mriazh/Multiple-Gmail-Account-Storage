"""Pytest configuration and shared fixtures."""

import os
import sys
import tempfile
import shutil

import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test isolation."""
    d = tempfile.mkdtemp(prefix="gam_test_")
    yield d
    if os.path.exists(d):
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    """
    Change working directory to a temp path so tests don't
    pollute the real project directory.
    """
    monkeypatch.chdir(tmp_path)
    # Create required subdirectories
    os.makedirs("config", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    return tmp_path
