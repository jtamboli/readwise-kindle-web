"""Storage for tracking articles hidden from Kindle."""
import json
import logging
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)

# Storage file path
STORAGE_FILE = Path("/data/hidden_articles.json")


class HiddenArticlesStorage:
    """Manages the set of article IDs that should be hidden from Kindle."""

    def __init__(self):
        """Initialize storage and load existing hidden articles."""
        self._hidden_ids: Set[str] = set()
        self._load()

    def _load(self):
        """Load hidden article IDs from disk."""
        if STORAGE_FILE.exists():
            try:
                with open(STORAGE_FILE, "r") as f:
                    data = json.load(f)
                    self._hidden_ids = set(data.get("hidden_ids", []))
                logger.info(f"Loaded {len(self._hidden_ids)} hidden article IDs from storage")
            except Exception as e:
                logger.warning(f"Error loading hidden articles: {e}. Starting with empty set.")
                self._hidden_ids = set()
        else:
            logger.info("No existing hidden articles storage found. Starting fresh.")
            self._hidden_ids = set()

    def _save(self):
        """Save hidden article IDs to disk."""
        try:
            # Ensure directory exists
            STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)

            with open(STORAGE_FILE, "w") as f:
                json.dump({"hidden_ids": list(self._hidden_ids)}, f, indent=2)
            logger.info(f"Saved {len(self._hidden_ids)} hidden article IDs to storage")
        except Exception as e:
            logger.error(f"Error saving hidden articles: {e}")

    def is_hidden(self, doc_id: str) -> bool:
        """
        Check if an article is hidden.

        Args:
            doc_id: Document ID

        Returns:
            True if the article is hidden, False otherwise
        """
        return doc_id in self._hidden_ids

    def hide(self, doc_id: str):
        """
        Mark an article as hidden.

        Args:
            doc_id: Document ID to hide
        """
        if doc_id not in self._hidden_ids:
            self._hidden_ids.add(doc_id)
            self._save()
            logger.info(f"Hid article {doc_id}")

    def unhide(self, doc_id: str):
        """
        Remove an article from the hidden list.

        Args:
            doc_id: Document ID to unhide
        """
        if doc_id in self._hidden_ids:
            self._hidden_ids.remove(doc_id)
            self._save()
            logger.info(f"Unhid article {doc_id}")

    def toggle(self, doc_id: str) -> bool:
        """
        Toggle the hidden status of an article.

        Args:
            doc_id: Document ID to toggle

        Returns:
            True if the article is now hidden, False if it's now visible
        """
        if doc_id in self._hidden_ids:
            self.unhide(doc_id)
            return False
        else:
            self.hide(doc_id)
            return True

    def get_hidden_ids(self) -> Set[str]:
        """
        Get all hidden article IDs.

        Returns:
            Set of hidden article IDs
        """
        return self._hidden_ids.copy()


# Singleton instance
hidden_storage = HiddenArticlesStorage()
