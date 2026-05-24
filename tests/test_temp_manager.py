"""Tests for crypto/temp_manager.py — secure temp directory management."""

import os
import tempfile

from crypto.temp_manager import (
    create_secure_temp,
    register_temp_dir,
    unregister_temp_dir,
    get_open_temp_dirs,
    cleanup_temp,
    cleanup_all_temp_dirs,
    scan_orphaned_temps,
    TEMP_PREFIX,
    _open_temp_dirs,
)


class TestCreateSecureTemp:
    def test_creates_directory(self):
        temp = create_secure_temp("TestGroup")
        try:
            assert os.path.isdir(temp)
            assert TEMP_PREFIX in os.path.basename(temp)
            assert "TestGroup" in os.path.basename(temp)
        finally:
            cleanup_temp(temp)

    def test_registered_on_creation(self):
        # Clear registry
        _open_temp_dirs.clear()
        temp = create_secure_temp("RegTest")
        try:
            assert temp in get_open_temp_dirs()
        finally:
            cleanup_temp(temp)


class TestRegistry:
    def test_register_unregister(self):
        _open_temp_dirs.clear()
        register_temp_dir("/fake/path")
        assert "/fake/path" in get_open_temp_dirs()
        unregister_temp_dir("/fake/path")
        assert "/fake/path" not in get_open_temp_dirs()

    def test_no_duplicates(self):
        _open_temp_dirs.clear()
        register_temp_dir("/same")
        register_temp_dir("/same")
        assert get_open_temp_dirs().count("/same") == 1
        _open_temp_dirs.clear()


class TestCleanup:
    def test_cleanup_removes_dir(self):
        temp = tempfile.mkdtemp(prefix=TEMP_PREFIX)
        # Add a file
        with open(os.path.join(temp, "test.txt"), "w") as f:
            f.write("data")
        cleanup_temp(temp)
        assert not os.path.exists(temp)

    def test_cleanup_nonexistent(self):
        # Should not raise
        cleanup_temp("/nonexistent/path/xyz")

    def test_cleanup_readonly_files(self):
        temp = tempfile.mkdtemp(prefix=TEMP_PREFIX)
        filepath = os.path.join(temp, "readonly.txt")
        with open(filepath, "w") as f:
            f.write("locked")
        os.chmod(filepath, 0o444)  # Read-only
        cleanup_temp(temp)
        assert not os.path.exists(temp)

    def test_cleanup_all(self):
        _open_temp_dirs.clear()
        t1 = tempfile.mkdtemp(prefix=TEMP_PREFIX)
        t2 = tempfile.mkdtemp(prefix=TEMP_PREFIX)
        register_temp_dir(t1)
        register_temp_dir(t2)

        cleanup_all_temp_dirs()
        assert not os.path.exists(t1)
        assert not os.path.exists(t2)
        assert len(get_open_temp_dirs()) == 0


class TestOrphanScan:
    def test_finds_orphans(self):
        # Create a fake orphan
        orphan = tempfile.mkdtemp(prefix=f"{TEMP_PREFIX}orphan_")
        try:
            orphans = scan_orphaned_temps()
            assert orphan in orphans
        finally:
            cleanup_temp(orphan)

    def test_no_false_positives(self):
        # Create a non-matching temp dir
        other = tempfile.mkdtemp(prefix="not_gam_")
        try:
            orphans = scan_orphaned_temps()
            assert other not in orphans
        finally:
            os.rmdir(other)
