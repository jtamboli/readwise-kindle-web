"""Tests for utility functions."""
import pytest

# Mock the config before importing utils to avoid KINDLE_READWISE_API_TOKEN validation
import sys
from unittest.mock import patch

# Patch Config.validate to avoid token validation during import
with patch.dict('os.environ', {'KINDLE_READWISE_API_TOKEN': 'test-token'}):
    from kindle_reader.utils import normalize_tags, deduplicate_by_id


class TestNormalizeTags:
    """Tests for normalize_tags function."""

    def test_normalize_dict_tags(self):
        """Should extract keys from dict-style tags."""
        tags = {"python": {}, "testing": {}, "web": {"extra": "data"}}
        result = normalize_tags(tags)
        assert result == ["python", "testing", "web"]

    def test_normalize_list_tags(self):
        """Should return list tags as-is."""
        tags = ["python", "testing", "web"]
        result = normalize_tags(tags)
        assert result == ["python", "testing", "web"]

    def test_normalize_empty_dict(self):
        """Should return empty list for empty dict."""
        result = normalize_tags({})
        assert result == []

    def test_normalize_empty_list(self):
        """Should return empty list for empty list."""
        result = normalize_tags([])
        assert result == []

    def test_normalize_none(self):
        """Should return empty list for None."""
        result = normalize_tags(None)
        assert result == []

    def test_normalize_string(self):
        """Should return empty list for unexpected string type."""
        result = normalize_tags("not-a-list-or-dict")
        assert result == []

    def test_normalize_number(self):
        """Should return empty list for unexpected number type."""
        result = normalize_tags(42)
        assert result == []

    def test_normalize_list_with_none_values(self):
        """Should filter out None values from list."""
        tags = ["python", None, "web"]
        result = normalize_tags(tags)
        assert result == ["python", "web"]

    def test_normalize_list_with_empty_strings(self):
        """Should filter out empty strings from list."""
        tags = ["python", "", "web"]
        result = normalize_tags(tags)
        assert result == ["python", "web"]


class TestDeduplicateById:
    """Tests for deduplicate_by_id function."""

    def test_deduplicate_removes_duplicates(self):
        """Should remove duplicate articles by ID."""
        items = [
            {"id": "1", "title": "First"},
            {"id": "2", "title": "Second"},
            {"id": "1", "title": "First Duplicate"},
            {"id": "3", "title": "Third"},
        ]
        result = deduplicate_by_id(items)
        assert len(result) == 3
        assert result[0]["title"] == "First"
        assert result[1]["title"] == "Second"
        assert result[2]["title"] == "Third"

    def test_deduplicate_preserves_order(self):
        """Should preserve original order of first occurrences."""
        items = [
            {"id": "3", "title": "Third"},
            {"id": "1", "title": "First"},
            {"id": "2", "title": "Second"},
            {"id": "1", "title": "First Again"},
        ]
        result = deduplicate_by_id(items)
        assert [item["id"] for item in result] == ["3", "1", "2"]

    def test_deduplicate_empty_list(self):
        """Should return empty list for empty input."""
        result = deduplicate_by_id([])
        assert result == []

    def test_deduplicate_no_duplicates(self):
        """Should return all items when no duplicates exist."""
        items = [
            {"id": "1", "title": "First"},
            {"id": "2", "title": "Second"},
            {"id": "3", "title": "Third"},
        ]
        result = deduplicate_by_id(items)
        assert len(result) == 3

    def test_deduplicate_missing_id(self):
        """Should skip items without an ID."""
        items = [
            {"id": "1", "title": "First"},
            {"title": "No ID"},
            {"id": "2", "title": "Second"},
            {"id": None, "title": "Null ID"},
        ]
        result = deduplicate_by_id(items)
        assert len(result) == 2
        assert result[0]["title"] == "First"
        assert result[1]["title"] == "Second"

    def test_deduplicate_all_duplicates(self):
        """Should return single item when all are duplicates."""
        items = [
            {"id": "1", "title": "First"},
            {"id": "1", "title": "First Again"},
            {"id": "1", "title": "First Yet Again"},
        ]
        result = deduplicate_by_id(items)
        assert len(result) == 1
        assert result[0]["title"] == "First"
