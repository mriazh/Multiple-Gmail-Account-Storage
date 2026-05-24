"""Tests for utils.py — atomic write operations."""

import json
import os

from utils import atomic_write_text, atomic_write_bytes, atomic_write_json


class TestAtomicWriteText:
    def test_creates_file(self, project_dir):
        atomic_write_text("test.txt", "hello world")
        assert os.path.exists("test.txt")
        with open("test.txt", "r") as f:
            assert f.read() == "hello world"

    def test_overwrites_existing(self, project_dir):
        atomic_write_text("test.txt", "first")
        atomic_write_text("test.txt", "second")
        with open("test.txt", "r") as f:
            assert f.read() == "second"

    def test_creates_parent_dirs(self, project_dir):
        atomic_write_text("sub/dir/test.txt", "nested")
        assert os.path.exists("sub/dir/test.txt")

    def test_unicode_content(self, project_dir):
        content = "こんにちは 🌍 émojis"
        atomic_write_text("unicode.txt", content)
        with open("unicode.txt", "r", encoding="utf-8") as f:
            assert f.read() == content

    def test_empty_content(self, project_dir):
        atomic_write_text("empty.txt", "")
        assert os.path.exists("empty.txt")
        with open("empty.txt", "r") as f:
            assert f.read() == ""


class TestAtomicWriteBytes:
    def test_creates_binary_file(self, project_dir):
        data = b"\x00\x01\x02\xff"
        atomic_write_bytes("test.bin", data)
        with open("test.bin", "rb") as f:
            assert f.read() == data

    def test_large_binary(self, project_dir):
        data = os.urandom(1024 * 100)  # 100KB
        atomic_write_bytes("large.bin", data)
        with open("large.bin", "rb") as f:
            assert f.read() == data


class TestAtomicWriteJson:
    def test_writes_json(self, project_dir):
        data = {"key": "value", "num": 42, "list": [1, 2, 3]}
        atomic_write_json("test.json", data)
        with open("test.json", "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_preserves_unicode(self, project_dir):
        data = {"name": "日本語テスト"}
        atomic_write_json("unicode.json", data)
        with open("unicode.json", "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_nested_structure(self, project_dir):
        data = {"a": {"b": {"c": [1, 2, {"d": True}]}}}
        atomic_write_json("nested.json", data)
        with open("nested.json", "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data
