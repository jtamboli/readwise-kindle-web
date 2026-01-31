"""Article filtering and sorting functions for Readwise Kindle Web Reader."""
from typing import List, Dict

from kindle_reader.utils import normalize_tags

# Tag used to mark articles as hidden from Kindle
KINDLE_HIDDEN_TAG = "kindle-hidden"


def is_article_hidden(article: Dict) -> bool:
    """
    Check if an article has the kindle-hidden tag.

    Args:
        article: Article dictionary

    Returns:
        True if article is hidden, False otherwise
    """
    tags = normalize_tags(article.get("tags"))
    return KINDLE_HIDDEN_TAG in tags


def filter_hidden_articles(items: List[Dict]) -> List[Dict]:
    """
    Filter out articles that are marked as hidden from Kindle.

    Articles with the 'kindle-hidden' tag are excluded from display.

    Args:
        items: List of document dictionaries

    Returns:
        List of documents with hidden articles removed
    """
    return [item for item in items if not is_article_hidden(item)]


def filter_seen_articles(items: List[Dict]) -> List[Dict]:
    """
    Filter out articles that have been seen (opened at least once).

    Articles with the 'seen' boolean flag set to True are excluded.

    Args:
        items: List of document dictionaries

    Returns:
        List of documents with seen articles removed
    """
    return [item for item in items if not item.get("seen")]


# Available sort options with their display names
SORT_OPTIONS = {
    "recent_activity": "Recent Activity",
    "saved_at": "Date Saved",
    "created_at": "Date Created",
    "updated_at": "Date Updated",
    "published_date": "Date Published",
    "first_opened_at": "First Opened",
    "last_opened_at": "Last Opened",
    "last_moved_at": "Last Moved",
}

DEFAULT_SORT = "recent_activity"


def sort_by_recent_activity(items: List[Dict]) -> List[Dict]:
    """
    Sort items by last_opened_at (most recent first), falling back to last_moved_at.

    For each item, uses last_opened_at if available, otherwise falls back to last_moved_at.
    All items are then sorted together by their respective timestamps in descending order.

    Args:
        items: List of document dictionaries

    Returns:
        Sorted list of documents
    """
    def sort_key(item: Dict) -> str:
        # Use last_opened_at if available, otherwise fall back to last_moved_at
        return item.get("last_opened_at") or item.get("last_moved_at", "")

    return sorted(items, key=sort_key, reverse=True)


def sort_by_field(items: List[Dict], field: str) -> List[Dict]:
    """
    Sort items by a specific date field (most recent first).

    Args:
        items: List of document dictionaries
        field: Field name to sort by

    Returns:
        Sorted list of documents
    """
    def sort_key(item: Dict) -> str:
        return item.get(field) or ""

    return sorted(items, key=sort_key, reverse=True)


def sort_items(items: List[Dict], sort_order: str = None) -> List[Dict]:
    """
    Sort items by the specified sort order.

    Args:
        items: List of document dictionaries
        sort_order: Sort order key from SORT_OPTIONS

    Returns:
        Sorted list of documents
    """
    if not sort_order or sort_order not in SORT_OPTIONS:
        sort_order = DEFAULT_SORT

    if sort_order == "recent_activity":
        return sort_by_recent_activity(items)
    else:
        return sort_by_field(items, sort_order)


def get_article_tags(article: Dict) -> List[str]:
    """
    Get the list of tag names for an article.

    Args:
        article: Article dictionary

    Returns:
        List of tag names
    """
    return normalize_tags(article.get("tags"))


def filter_by_tag(items: List[Dict], tag_name: str) -> List[Dict]:
    """
    Filter articles that have a specific tag.

    Args:
        items: List of document dictionaries
        tag_name: Name of the tag to filter by

    Returns:
        List of documents that have the specified tag
    """
    return [item for item in items if tag_name in get_article_tags(item)]
