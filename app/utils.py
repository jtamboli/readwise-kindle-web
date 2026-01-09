"""Shared utility functions for Readwise Kindle Web Reader."""
from typing import List, Dict, Any


def normalize_tags(tags: Any) -> List[str]:
    """
    Normalize tags to a list of strings.

    The Readwise API can return tags in different formats:
    - As a dict with tag names as keys: {"tag1": {...}, "tag2": {...}}
    - As a list of strings: ["tag1", "tag2"]
    - As None or other types

    Args:
        tags: Tags in various formats (dict, list, or None)

    Returns:
        List of tag names as strings
    """
    if isinstance(tags, dict):
        return list(tags.keys())
    elif isinstance(tags, list):
        return [str(t) for t in tags if t]
    else:
        return []


def deduplicate_by_id(items: List[Dict]) -> List[Dict]:
    """
    Remove duplicate articles by ID, preserving order.

    Args:
        items: List of article dictionaries with 'id' field

    Returns:
        List of unique articles (first occurrence kept)
    """
    seen_ids: set = set()
    unique_items: List[Dict] = []

    for item in items:
        item_id = item.get("id")
        if item_id and item_id not in seen_ids:
            seen_ids.add(item_id)
            unique_items.append(item)

    return unique_items
