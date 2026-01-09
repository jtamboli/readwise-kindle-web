"""Shared test fixtures for Readwise Kindle Web Reader tests."""
import pytest


@pytest.fixture
def sample_article_with_dict_tags():
    """Article with tags as a dictionary (common API format)."""
    return {
        "id": "article-1",
        "title": "Test Article",
        "author": "Test Author",
        "source": "https://example.com/article",
        "word_count": 1000,
        "tags": {"python": {}, "testing": {}, "kindle-hidden": {}},
        "reading_progress": 0.5,
        "last_opened_at": "2024-01-15T10:00:00Z",
        "last_moved_at": "2024-01-10T08:00:00Z",
        "seen": True,
    }


@pytest.fixture
def sample_article_with_list_tags():
    """Article with tags as a list."""
    return {
        "id": "article-2",
        "title": "Another Article",
        "author": "Another Author",
        "source": "https://example.org/post",
        "word_count": 500,
        "tags": ["python", "web"],
        "reading_progress": 0,
        "last_opened_at": None,
        "last_moved_at": "2024-01-12T14:00:00Z",
        "seen": False,
    }


@pytest.fixture
def sample_article_no_tags():
    """Article with no tags."""
    return {
        "id": "article-3",
        "title": "No Tags Article",
        "author": None,
        "source": "https://example.net/page",
        "word_count": 250,
        "tags": None,
        "reading_progress": 0,
        "last_opened_at": None,
        "last_moved_at": "2024-01-05T12:00:00Z",
        "seen": False,
    }


@pytest.fixture
def sample_hidden_article():
    """Article marked as hidden from Kindle."""
    return {
        "id": "article-hidden",
        "title": "Hidden Article",
        "author": "Hidden Author",
        "source": "https://example.com/hidden",
        "word_count": 300,
        "tags": {"kindle-hidden": {}},
        "reading_progress": 0,
        "last_opened_at": None,
        "last_moved_at": "2024-01-08T09:00:00Z",
        "seen": False,
    }


@pytest.fixture
def sample_visible_article():
    """Article that is not hidden."""
    return {
        "id": "article-visible",
        "title": "Visible Article",
        "author": "Visible Author",
        "source": "https://example.com/visible",
        "word_count": 400,
        "tags": {"tech": {}, "news": {}},
        "reading_progress": 0.25,
        "last_opened_at": "2024-01-14T16:00:00Z",
        "last_moved_at": "2024-01-07T11:00:00Z",
        "seen": False,
    }


@pytest.fixture
def article_list():
    """List of articles for testing filters and sorting."""
    return [
        {
            "id": "1",
            "title": "First",
            "tags": {"python": {}},
            "last_opened_at": "2024-01-10T10:00:00Z",
            "last_moved_at": "2024-01-05T08:00:00Z",
            "seen": False,
        },
        {
            "id": "2",
            "title": "Second",
            "tags": {"kindle-hidden": {}},
            "last_opened_at": None,
            "last_moved_at": "2024-01-15T12:00:00Z",
            "seen": False,
        },
        {
            "id": "3",
            "title": "Third",
            "tags": ["python", "web"],
            "last_opened_at": "2024-01-12T14:00:00Z",
            "last_moved_at": "2024-01-01T10:00:00Z",
            "seen": True,
        },
        {
            "id": "4",
            "title": "Fourth",
            "tags": {},
            "last_opened_at": None,
            "last_moved_at": "2024-01-08T09:00:00Z",
            "seen": False,
        },
    ]
