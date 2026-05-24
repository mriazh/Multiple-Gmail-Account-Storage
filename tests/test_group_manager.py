"""Tests for accounts/group_manager.py — group CRUD and validation."""

import os
import json

import pytest

from accounts.group_manager import (
    list_groups,
    create_group,
    validate_name,
    get_all_group_names,
    group_exists,
    resolve_group_input,
)
from accounts.credential_store import save


class TestValidateName:
    def test_valid_names(self):
        valid = ["Group_1", "my-group", "Test123", "a_b-c", "A"]
        for name in valid:
            is_valid, err = validate_name(name)
            assert is_valid, f"'{name}' should be valid but got: {err}"

    def test_empty_name(self):
        is_valid, _ = validate_name("")
        assert not is_valid

    def test_too_long(self):
        is_valid, _ = validate_name("a" * 51)
        assert not is_valid

    def test_special_characters(self):
        invalid = ["hello world", "test@group", "a/b", "a\\b", "a.b", "a!b"]
        for name in invalid:
            is_valid, _ = validate_name(name)
            assert not is_valid, f"'{name}' should be invalid"

    def test_path_traversal(self):
        is_valid, _ = validate_name("..test")
        assert not is_valid

    def test_starts_with_dot(self):
        is_valid, _ = validate_name(".hidden")
        assert not is_valid

    def test_starts_with_dash(self):
        is_valid, _ = validate_name("-invalid")
        assert not is_valid

    def test_reserved_windows_names(self):
        reserved = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1", "con", "Con"]
        for name in reserved:
            is_valid, _ = validate_name(name)
            assert not is_valid, f"'{name}' should be rejected as reserved"

    def test_duplicate_detection(self, project_dir):
        save({"Existing": []})
        is_valid, _ = validate_name("existing")  # case-insensitive
        assert not is_valid


class TestCreateGroup:
    def test_auto_increment_first(self, project_dir):
        name = create_group()
        assert name == "Group_1"

    def test_auto_increment_sequential(self, project_dir):
        save({"Group_1": [], "Group_2": []})
        name = create_group()
        assert name == "Group_3"

    def test_custom_name(self, project_dir):
        name = create_group("MyCustom")
        assert name == "MyCustom"

    def test_custom_invalid_raises(self, project_dir):
        with pytest.raises(ValueError):
            create_group("invalid name!")

    def test_creates_entry_in_accounts(self, project_dir):
        create_group("NewGroup")
        from accounts.credential_store import load
        data = load()
        assert "NewGroup" in data
        assert data["NewGroup"] == []


class TestListGroups:
    def test_empty(self, project_dir):
        groups = list_groups()
        assert groups == []

    def test_with_accounts(self, project_dir):
        save({
            "Group_1": [{"email": "a@b.com", "password": "x", "salt": "s"}],
            "Group_2": [
                {"email": "c@d.com", "password": "x", "salt": "s"},
                {"email": "e@f.com", "password": "x", "salt": "s"},
            ],
        })
        groups = list_groups()
        assert len(groups) == 2
        # Find Group_1
        g1 = next(g for g in groups if g["name"] == "Group_1")
        assert g1["count"] == 1
        g2 = next(g for g in groups if g["name"] == "Group_2")
        assert g2["count"] == 2


class TestGetAllGroupNames:
    def test_from_json_only(self, project_dir):
        save({"Alpha": [], "Beta": []})
        names = get_all_group_names()
        assert "Alpha" in names
        assert "Beta" in names

    def test_from_enc_files(self, project_dir):
        # Create .enc files
        with open("Gamma.enc", "wb") as f:
            f.write(b"data")
        names = get_all_group_names()
        assert "Gamma" in names

    def test_combined(self, project_dir):
        save({"FromJson": []})
        with open("FromEnc.enc", "wb") as f:
            f.write(b"data")
        names = get_all_group_names()
        assert "FromJson" in names
        assert "FromEnc" in names

    def test_excludes_bak(self, project_dir):
        with open("Backup.enc.bak", "wb") as f:
            f.write(b"data")
        names = get_all_group_names()
        assert "Backup.enc" not in names


class TestResolveGroupInput:
    def test_by_number(self, project_dir):
        save({"Alpha": [], "Beta": []})
        # Sorted: Alpha=1, Beta=2
        result = resolve_group_input("1")
        assert result in ["Alpha", "Beta"]  # depends on sort

    def test_by_name(self, project_dir):
        save({"MyGroup": []})
        result = resolve_group_input("MyGroup")
        assert result == "MyGroup"

    def test_by_name_case_insensitive(self, project_dir):
        save({"MyGroup": []})
        result = resolve_group_input("mygroup")
        assert result == "MyGroup"

    def test_invalid_number(self, project_dir):
        save({"Only": []})
        result = resolve_group_input("99")
        assert result is None

    def test_nonexistent_name(self, project_dir):
        result = resolve_group_input("nope")
        assert result is None


class TestGroupExists:
    def test_exists(self, project_dir):
        save({"Test": []})
        assert group_exists("Test") is True
        assert group_exists("test") is True  # case-insensitive

    def test_not_exists(self, project_dir):
        assert group_exists("Nope") is False
