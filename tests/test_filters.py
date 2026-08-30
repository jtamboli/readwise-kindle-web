"""Tests for filter functions."""
import pytest
from unittest.mock import patch

# Patch Config.validate to avoid token validation during import
with patch.dict('os.environ', {'KINDLE_READWISE_API_TOKEN': 'test-token'}):
    from kindle_reader.filters import (
        KINDLE_HIDDEN_TAG,
        is_article_hidden,
        filter_hidden_articles,
        filter_seen_articles,
        is_article_seen,
        sort_by_recent_activity,
        get_article_tags,
        filter_by_tag,
    )


class TestKindleHiddenTag:
    """Tests for KINDLE_HIDDEN_TAG constant."""

    def test_hidden_tag_value(self):
        """Should have correct tag name."""
        assert KINDLE_HIDDEN_TAG == "kindle-hidden"


class TestIsArticleHidden:
    """Tests for is_article_hidden function."""

    def test_hidden_with_dict_tags(self, sample_article_with_dict_tags):
        """Should detect hidden article with dict tags."""
        assert is_article_hidden(sample_article_with_dict_tags) is True

    def test_hidden_with_list_tags(self):
        """Should detect hidden article with list tags."""
        article = {"id": "1", "tags": ["kindle-hidden", "other"]}
        assert is_article_hidden(article) is True

    def test_not_hidden_with_dict_tags(self, sample_visible_article):
        """Should return False for visible article with dict tags."""
        assert is_article_hidden(sample_visible_article) is False

    def test_not_hidden_with_list_tags(self, sample_article_with_list_tags):
        """Should return False for article without hidden tag."""
        assert is_article_hidden(sample_article_with_list_tags) is False

    def test_not_hidden_no_tags(self, sample_article_no_tags):
        """Should return False for article with no tags."""
        assert is_article_hidden(sample_article_no_tags) is False

    def test_not_hidden_empty_tags(self):
        """Should return False for article with empty tags."""
        article = {"id": "1", "tags": {}}
        assert is_article_hidden(article) is False


class TestFilterHiddenArticles:
    """Tests for filter_hidden_articles function."""

    def test_filters_hidden_articles(self, article_list):
        """Should remove articles with kindle-hidden tag."""
        result = filter_hidden_articles(article_list)
        assert len(result) == 3
        assert all(item["id"] != "2" for item in result)

    def test_empty_list(self):
        """Should return empty list for empty input."""
        result = filter_hidden_articles([])
        assert result == []

    def test_all_hidden(self):
        """Should return empty list when all articles are hidden."""
        articles = [
            {"id": "1", "tags": {"kindle-hidden": {}}},
            {"id": "2", "tags": ["kindle-hidden"]},
        ]
        result = filter_hidden_articles(articles)
        assert result == []

    def test_none_hidden(self):
        """Should return all articles when none are hidden."""
        articles = [
            {"id": "1", "tags": {"python": {}}},
            {"id": "2", "tags": ["web"]},
        ]
        result = filter_hidden_articles(articles)
        assert len(result) == 2


class TestFilterSeenArticles:
    """Tests for filter_seen_articles function."""

    def test_filters_seen_articles(self, article_list):
        """Should remove articles flagged seen or carrying an open timestamp."""
        result = filter_seen_articles(article_list)
        ids = [item["id"] for item in result]
        assert ids == ["2", "4"]

    def test_empty_list(self):
        """Should return empty list for empty input."""
        result = filter_seen_articles([])
        assert result == []

    def test_all_seen(self):
        """Should return empty list when all articles are seen."""
        articles = [
            {"id": "1", "seen": True},
            {"id": "2", "seen": True},
        ]
        result = filter_seen_articles(articles)
        assert result == []

    def test_none_seen(self):
        """Should return all articles when none are seen."""
        articles = [
            {"id": "1", "seen": False},
            {"id": "2", "seen": False},
        ]
        result = filter_seen_articles(articles)
        assert len(result) == 2

    def test_missing_seen_field(self):
        """Should keep articles with no seen signal at all."""
        articles = [
            {"id": "1"},
            {"id": "2", "seen": True},
        ]
        result = filter_seen_articles(articles)
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_filters_by_first_opened_at(self):
        """Should treat a first_opened_at timestamp as seen."""
        articles = [
            {"id": "1", "first_opened_at": "2024-01-10T10:00:00Z"},
            {"id": "2", "first_opened_at": None},
        ]
        result = filter_seen_articles(articles)
        assert [item["id"] for item in result] == ["2"]

    def test_filters_by_last_opened_at(self):
        """Should treat a last_opened_at timestamp as seen."""
        articles = [
            {"id": "1", "last_opened_at": "2024-01-10T10:00:00Z"},
            {"id": "2", "last_opened_at": None},
        ]
        result = filter_seen_articles(articles)
        assert [item["id"] for item in result] == ["2"]

    def test_filters_by_reading_progress(self):
        """Should treat non-zero reading progress as seen."""
        articles = [
            {"id": "1", "reading_progress": 0.3},
            {"id": "2", "reading_progress": 0},
            {"id": "3", "reading_progress": None},
        ]
        result = filter_seen_articles(articles)
        assert [item["id"] for item in result] == ["2", "3"]

    def test_filters_by_locally_seen_ids(self):
        """Should exclude articles opened in this reader."""
        articles = [
            {"id": "1"},
            {"id": "2"},
        ]
        result = filter_seen_articles(articles, {"1"})
        assert [item["id"] for item in result] == ["2"]

    def test_empty_seen_ids_keeps_unopened(self):
        """Should keep everything when no article has been opened."""
        articles = [
            {"id": "1"},
            {"id": "2"},
        ]
        result = filter_seen_articles(articles, set())
        assert len(result) == 2


class TestIsArticleSeen:
    """Tests for is_article_seen function."""

    def test_unopened_article_is_unseen(self):
        """Should return False for an article with no open signal."""
        article = {
            "id": "1",
            "first_opened_at": None,
            "last_opened_at": None,
            "reading_progress": 0,
        }
        assert is_article_seen(article) is False

    def test_opened_article_is_seen(self):
        """Should return True once an open timestamp exists."""
        article = {"id": "1", "last_opened_at": "2024-01-10T10:00:00Z"}
        assert is_article_seen(article) is True

    def test_locally_opened_article_is_seen(self):
        """Should return True for an ID in the local seen set."""
        assert is_article_seen({"id": "1"}, {"1"}) is True


class TestSortByRecentActivity:
    """Tests for sort_by_recent_activity function."""

    def test_sorts_by_last_opened_at(self):
        """Should sort by last_opened_at in descending order."""
        articles = [
            {"id": "1", "last_opened_at": "2024-01-10T10:00:00Z"},
            {"id": "2", "last_opened_at": "2024-01-15T12:00:00Z"},
            {"id": "3", "last_opened_at": "2024-01-12T14:00:00Z"},
        ]
        result = sort_by_recent_activity(articles)
        assert [item["id"] for item in result] == ["2", "3", "1"]

    def test_falls_back_to_last_moved_at(self):
        """Should use last_moved_at when last_opened_at is None."""
        articles = [
            {"id": "1", "last_opened_at": None, "last_moved_at": "2024-01-10T10:00:00Z"},
            {"id": "2", "last_opened_at": "2024-01-15T12:00:00Z", "last_moved_at": "2024-01-01T10:00:00Z"},
            {"id": "3", "last_opened_at": None, "last_moved_at": "2024-01-12T14:00:00Z"},
        ]
        result = sort_by_recent_activity(articles)
        assert [item["id"] for item in result] == ["2", "3", "1"]

    def test_empty_list(self):
        """Should return empty list for empty input."""
        result = sort_by_recent_activity([])
        assert result == []

    def test_missing_fields(self):
        """Should handle articles with missing timestamp fields."""
        articles = [
            {"id": "1"},
            {"id": "2", "last_opened_at": "2024-01-15T12:00:00Z"},
        ]
        result = sort_by_recent_activity(articles)
        assert result[0]["id"] == "2"
        assert result[1]["id"] == "1"


class TestGetArticleTags:
    """Tests for get_article_tags function."""

    def test_get_tags_from_dict(self, sample_article_with_dict_tags):
        """Should extract tag names from dict tags."""
        result = get_article_tags(sample_article_with_dict_tags)
        assert "python" in result
        assert "testing" in result
        assert "kindle-hidden" in result

    def test_get_tags_from_list(self, sample_article_with_list_tags):
        """Should return list tags."""
        result = get_article_tags(sample_article_with_list_tags)
        assert result == ["python", "web"]

    def test_get_tags_from_none(self, sample_article_no_tags):
        """Should return empty list for None tags."""
        result = get_article_tags(sample_article_no_tags)
        assert result == []


class TestFilterByTag:
    """Tests for filter_by_tag function."""

    def test_filter_by_existing_tag(self, article_list):
        """Should return articles with the specified tag."""
        result = filter_by_tag(article_list, "python")
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["id"] == "3"

    def test_filter_by_nonexistent_tag(self, article_list):
        """Should return empty list for tag that doesn't exist."""
        result = filter_by_tag(article_list, "nonexistent")
        assert result == []

    def test_filter_empty_list(self):
        """Should return empty list for empty input."""
        result = filter_by_tag([], "python")
        assert result == []

    def test_filter_by_hidden_tag(self, article_list):
        """Should find articles with kindle-hidden tag."""
        result = filter_by_tag(article_list, "kindle-hidden")
        assert len(result) == 1
        assert result[0]["id"] == "2"
