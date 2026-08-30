"""Async Readwise API client with caching."""
import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional
import httpx
from cachetools import TTLCache
from kindle_reader.config import Config
from kindle_reader.utils import normalize_tags, deduplicate_by_id


# Configure logging
logging.basicConfig(
    level=logging.INFO if Config.KINDLE_READWISE_VERBOSE else logging.WARNING,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# Two-tier caching
# Support multiple location caches (shortlist, later, feed, etc.)
list_cache = TTLCache(maxsize=10, ttl=Config.KINDLE_CACHE_LIST_TTL)
document_cache: Dict[str, Dict] = {}  # No TTL, invalidated manually

# Valid locations for the API
VALID_LOCATIONS = {"new", "later", "shortlist", "archive", "feed"}


class ReadwiseClient:
    """Async client for Readwise Reader API."""

    def __init__(self):
        self.base_url = Config.READWISE_API_BASE
        self.headers = {
            "Authorization": f"Token {Config.KINDLE_READWISE_API_TOKEN}",
            "Content-Type": "application/json",
        }

    async def get_items_by_location(self, location: str, limit: int = 100) -> List[Dict]:
        """
        Fetch items from a specific location.

        Args:
            location: One of 'new', 'later', 'shortlist', 'archive', 'feed'
            limit: Maximum number of items to fetch (default 100)

        Returns:
            List of document metadata dictionaries.
        """
        if location not in VALID_LOCATIONS:
            raise ValueError(f"Invalid location: {location}. Must be one of {VALID_LOCATIONS}")

        # Check cache
        cache_key = f"list_{location}_{limit}"
        if cache_key in list_cache:
            logger.info(f"Loading {location} items from cache")
            return list_cache[cache_key]

        logger.info(f"Fetching {location} items from Readwise API (max {limit} items)")

        # Fetch from API
        async with httpx.AsyncClient() as client:
            all_results = []
            next_cursor = None
            page_num = 1

            while len(all_results) < limit:
                params = {"location": location}
                if next_cursor:
                    params["pageCursor"] = next_cursor

                logger.info(f"  → API request: GET /list/ (page {page_num}, location={location})")

                response = await client.get(
                    f"{self.base_url}/list/",
                    headers=self.headers,
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()

                data = response.json()
                page_results = data.get("results", [])
                all_results.extend(page_results)

                logger.info(f"  ← Received {len(page_results)} items (total: {len(all_results)})")

                next_cursor = data.get("nextPageCursor")
                if not next_cursor:
                    break

                page_num += 1

            # Trim to limit if we fetched more
            all_results = all_results[:limit]

            # Cache the results
            list_cache[cache_key] = all_results
            logger.info(f"Cached {len(all_results)} {location} items")
            return all_results

    async def get_document(self, doc_id: str) -> Optional[Dict]:
        """
        Fetch a single document with HTML content.

        Args:
            doc_id: Document ID

        Returns:
            Document dictionary with html_content field.
        """
        # Check cache
        if doc_id in document_cache:
            logger.info(f"Loading document {doc_id} from cache")
            return document_cache[doc_id]

        logger.info(f"Fetching document {doc_id} with HTML content from Readwise API")

        # Fetch from API
        async with httpx.AsyncClient() as client:
            params = {"id": doc_id, "withHtmlContent": "true"}

            logger.info(f"  → API request: GET /list/ (id={doc_id}, withHtmlContent=true)")

            response = await client.get(
                f"{self.base_url}/list/",
                headers=self.headers,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            if not results:
                logger.info(f"  ← Document {doc_id} not found")
                return None

            document = results[0]
            title = document.get("title", "Untitled")
            html_length = len(document.get("html_content", ""))

            logger.info(f"  ← Received document: '{title}' ({html_length} bytes HTML)")

            # Cache the document
            document_cache[doc_id] = document
            logger.info(f"Cached document {doc_id}")
            return document

    async def mark_document_seen(self, doc_id: str):
        """
        Mark a document as seen, the same state the official Reader apps set.

        The API populates first_opened_at / last_opened_at in response; those
        timestamps are what the Feed list reads back to decide seen state.
        Cached copies are stamped locally so the item drops out of the Feed
        without waiting for the list cache to expire.

        Args:
            doc_id: Document ID
        """
        logger.info(f"Marking document {doc_id} as seen")

        async with httpx.AsyncClient() as client:
            logger.info(f"  → API request: PATCH /update/{doc_id}/ (seen=true)")

            response = await client.patch(
                f"{self.base_url}/update/{doc_id}/",
                headers=self.headers,
                json={"seen": True},
                timeout=10.0,
            )
            response.raise_for_status()

            logger.info(f"  ← Document marked as seen")

        self._stamp_seen_in_caches(doc_id)

    def _stamp_seen_in_caches(self, doc_id: str):
        """
        Mirror a seen marking onto cached copies of a document.

        Args:
            doc_id: Document ID
        """
        now = datetime.now(timezone.utc).isoformat()

        def stamp(document: Dict):
            document["last_opened_at"] = now
            if not document.get("first_opened_at"):
                document["first_opened_at"] = now

        if doc_id in document_cache:
            stamp(document_cache[doc_id])

        for items in list_cache.values():
            for item in items:
                if item.get("id") == doc_id:
                    stamp(item)

    def update_reading_progress(self, doc_id: str, progress: float):
        """
        Update reading progress for a document locally.

        The Readwise public API doesn't support writing reading_progress
        (it's read-only), so we only update the local cache.

        Args:
            doc_id: Document ID
            progress: Reading progress (0.0 to 1.0)
        """
        if doc_id in document_cache:
            document_cache[doc_id]["reading_progress"] = progress
            logger.info(f"Updated cached reading progress for {doc_id} to {progress:.1%}")

    async def archive_document(self, doc_id: str):
        """
        Archive a document and invalidate caches.

        Args:
            doc_id: Document ID
        """
        logger.info(f"Archiving document {doc_id}")

        async with httpx.AsyncClient() as client:
            logger.info(f"  → API request: PATCH /update/{doc_id}/ (location=archive)")

            response = await client.patch(
                f"{self.base_url}/update/{doc_id}/",
                headers=self.headers,
                json={"location": "archive"},
                timeout=10.0,
            )
            response.raise_for_status()

            logger.info(f"  ← Document archived successfully")

        # Invalidate caches
        self.invalidate_document_cache(doc_id)
        self.invalidate_list_cache()

    def invalidate_document_cache(self, doc_id: str):
        """Invalidate cached document."""
        if doc_id in document_cache:
            del document_cache[doc_id]
            logger.info(f"Invalidated document cache for {doc_id}")

    def invalidate_list_cache(self):
        """Invalidate cached inbox list."""
        list_cache.clear()
        logger.info("Invalidated inbox list cache")

    async def get_library_articles(self, limit_per_location: int = 100) -> List[Dict]:
        """
        Fetch articles from library locations (later and shortlist).
        Used for tag aggregation and filtering.

        Args:
            limit_per_location: Maximum number of items to fetch per location

        Returns:
            List of article metadata dictionaries from library locations.
        """
        # Only fetch from later and shortlist locations
        active_locations = {"later", "shortlist"}

        # Check cache
        cache_key = f"library_articles_{limit_per_location}"
        if cache_key in list_cache:
            logger.info("Loading library articles from cache")
            return list_cache[cache_key]

        logger.info("Fetching articles from library locations for tags (later, shortlist)")

        # Fetch from active locations
        all_articles = []
        for location in active_locations:
            try:
                items = await self.get_items_by_location(location, limit=limit_per_location)
                all_articles.extend(items)
            except Exception as e:
                logger.warning(f"Error fetching {location} items: {e}")
                continue

        # Remove duplicates by ID (in case an article appears in multiple locations)
        unique_articles = deduplicate_by_id(all_articles)

        # Cache the results
        list_cache[cache_key] = unique_articles
        logger.info(f"Cached {len(unique_articles)} unique articles")
        return unique_articles

    async def toggle_tag(self, doc_id: str, tag: str, current_article_data: Optional[Dict] = None) -> bool:
        """
        Toggle a tag on an article (add if not present, remove if present).

        Args:
            doc_id: Document ID
            tag: Tag name to toggle
            current_article_data: Optional current article data to avoid extra API call

        Returns:
            True if tag was added, False if it was removed
        """
        logger.info(f"Toggling tag '{tag}' on document {doc_id}")

        # Get current tags using shared utility
        if current_article_data:
            current_tags = normalize_tags(current_article_data.get("tags", []))
        else:
            # Fetch current article data to get tags
            article = await self.get_document(doc_id)
            if not article:
                raise ValueError(f"Document {doc_id} not found")
            current_tags = normalize_tags(article.get("tags", []))

        # Toggle the tag
        if tag in current_tags:
            # Remove the tag
            new_tags = [t for t in current_tags if t != tag]
            added = False
            logger.info(f"Removing tag '{tag}' from document {doc_id}")
        else:
            # Add the tag
            new_tags = current_tags + [tag]
            added = True
            logger.info(f"Adding tag '{tag}' to document {doc_id}")

        # Update the article with new tags
        async with httpx.AsyncClient() as client:
            logger.info(f"  → API request: PATCH /update/{doc_id}/ (tags={new_tags})")

            response = await client.patch(
                f"{self.base_url}/update/{doc_id}/",
                headers=self.headers,
                json={"tags": new_tags},
                timeout=10.0,
            )
            response.raise_for_status()

            logger.info(f"  ← Tags updated successfully")

        # Invalidate caches
        self.invalidate_document_cache(doc_id)
        self.invalidate_list_cache()

        return added


# Singleton instance
client = ReadwiseClient()
