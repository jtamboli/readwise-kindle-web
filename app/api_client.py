"""Async Readwise API client with caching."""
import asyncio
import logging
import sys
from typing import List, Dict, Optional
import httpx
from cachetools import TTLCache
from kindle_reader.config import Config


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
list_cache = TTLCache(maxsize=10, ttl=Config.CACHE_LIST_TTL)
document_cache: Dict[str, Dict] = {}  # No TTL, invalidated manually

# Valid locations for the API
VALID_LOCATIONS = {"new", "later", "shortlist", "archive", "feed"}


class ReadwiseClient:
    """Async client for Readwise Reader API."""

    def __init__(self):
        self.base_url = Config.READWISE_API_BASE
        self.headers = {
            "Authorization": f"Token {Config.READWISE_API_TOKEN}",
            "Content-Type": "application/json",
        }

    async def get_inbox_items(self) -> List[Dict]:
        """
        Fetch inbox items from Readwise Reader API.

        Returns:
            List of document metadata dictionaries.
        """
        # Check cache
        cache_key = "inbox_list"
        if cache_key in list_cache:
            logger.info("Loading inbox items from cache")
            return list_cache[cache_key]

        logger.info("Fetching inbox items from Readwise API (Later library, max 100 items)")

        # Fetch from API (limit to most recent 100 items to avoid rate limits)
        async with httpx.AsyncClient() as client:
            all_results = []
            next_cursor = None
            max_items = 100
            page_num = 1

            while len(all_results) < max_items:
                params = {"location": "later"}
                if next_cursor:
                    params["pageCursor"] = next_cursor

                logger.info(f"  → API request: GET /list/ (page {page_num}, location=later)")

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

            # Trim to max_items if we fetched more
            all_results = all_results[:max_items]

            # Cache the results
            list_cache[cache_key] = all_results
            logger.info(f"Cached {len(all_results)} inbox items")
            return all_results

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

    async def update_reading_progress(self, doc_id: str, progress: float):
        """
        Update reading progress for a document (fire-and-forget).

        Args:
            doc_id: Document ID
            progress: Reading progress (0.0 to 1.0)
        """
        logger.info(f"Updating reading progress for document {doc_id} to {progress:.1%}")

        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"  → API request: PATCH /update/{doc_id}/ (reading_progress={progress:.2f})")

                response = await client.patch(
                    f"{self.base_url}/update/{doc_id}/",
                    headers=self.headers,
                    json={"reading_progress": progress},
                    timeout=10.0,
                )
                response.raise_for_status()

                logger.info(f"  ← Progress updated successfully")
        except Exception as e:
            # Log error but don't raise (fire-and-forget)
            logger.warning(f"Error updating reading progress for {doc_id}: {e}")

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
        if doc_id in document_cache:
            del document_cache[doc_id]
            logger.info(f"Invalidated document cache for {doc_id}")

        list_cache.clear()
        logger.info("Invalidated inbox list cache")

    def invalidate_document_cache(self, doc_id: str):
        """Invalidate cached document."""
        if doc_id in document_cache:
            del document_cache[doc_id]
            logger.info(f"Invalidated document cache for {doc_id}")

    def invalidate_list_cache(self):
        """Invalidate cached inbox list."""
        list_cache.clear()
        logger.info("Invalidated inbox list cache")

    async def get_all_articles(self, limit_per_location: int = 100) -> List[Dict]:
        """
        Fetch articles from all locations to gather tags.

        Args:
            limit_per_location: Maximum number of items to fetch per location

        Returns:
            List of all article metadata dictionaries from all locations.
        """
        # Check cache
        cache_key = f"all_articles_{limit_per_location}"
        if cache_key in list_cache:
            logger.info("Loading all articles from cache")
            return list_cache[cache_key]

        logger.info("Fetching articles from all locations for tags")

        # Fetch from all locations
        all_articles = []
        for location in VALID_LOCATIONS:
            try:
                items = await self.get_items_by_location(location, limit=limit_per_location)
                all_articles.extend(items)
            except Exception as e:
                logger.warning(f"Error fetching {location} items: {e}")
                continue

        # Remove duplicates by ID (in case an article appears in multiple locations)
        seen_ids = set()
        unique_articles = []
        for article in all_articles:
            article_id = article.get("id")
            if article_id and article_id not in seen_ids:
                seen_ids.add(article_id)
                unique_articles.append(article)

        # Cache the results
        list_cache[cache_key] = unique_articles
        logger.info(f"Cached {len(unique_articles)} unique articles")
        return unique_articles


# Singleton instance
client = ReadwiseClient()
