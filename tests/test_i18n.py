"""Tests for i18n module — bilingual string system."""

from i18n import set_language, get_language, t


class TestSetLanguage:
    def test_set_english(self):
        set_language("en")
        assert get_language() == "en"

    def test_set_indonesian(self):
        set_language("id")
        assert get_language() == "id"

    def test_invalid_language_raises(self):
        import pytest
        with pytest.raises(ValueError):
            set_language("fr")


class TestTranslation:
    def test_english_key(self):
        set_language("en")
        result = t("menu.check")
        assert "Check" in result

    def test_indonesian_key(self):
        set_language("id")
        result = t("menu.check")
        assert "Cek" in result

    def test_missing_key(self):
        set_language("en")
        result = t("nonexistent.key")
        assert result == "[MISSING: nonexistent.key]"

    def test_format_placeholder(self):
        set_language("en")
        result = t("auth.login.wrong", remaining=5)
        assert "5" in result

    def test_format_multiple_placeholders(self):
        set_language("en")
        result = t("add.email_duplicate", email="test@gmail.com", group="Group_1")
        assert "test@gmail.com" in result
        assert "Group_1" in result

    def test_all_english_keys_exist(self):
        """Verify all English keys have values (not None)."""
        from i18n.en import STRINGS
        set_language("en")
        for key in STRINGS:
            result = t(key)
            assert "[MISSING:" not in result, f"Key '{key}' missing in English"

    def test_all_indonesian_keys_exist(self):
        """Verify all Indonesian keys have values."""
        from i18n.id import STRINGS
        set_language("id")
        for key in STRINGS:
            result = t(key)
            assert "[MISSING:" not in result, f"Key '{key}' missing in Indonesian"

    def test_key_parity(self):
        """Both languages should have the same keys."""
        from i18n.en import STRINGS as EN
        from i18n.id import STRINGS as ID
        en_keys = set(EN.keys())
        id_keys = set(ID.keys())
        missing_in_id = en_keys - id_keys
        missing_in_en = id_keys - en_keys
        assert not missing_in_id, f"Keys in EN but not ID: {missing_in_id}"
        assert not missing_in_en, f"Keys in ID but not EN: {missing_in_en}"
