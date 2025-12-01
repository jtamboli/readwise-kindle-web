"""Async Readwise API client with caching."""
import asyncio
from typing import List, Dict, Optional
import httpx
from cachetools import TTLCache
from app.config import Config


# Two-tier caching
list_cache = TTLCache(maxsize=1, ttl=Config.CACHE_LIST_TTL)
document_cache: Dict[str, Dict] = {}  # No TTL, invalidated manually


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
            return list_cache[cache_key]

        # Fetch from API
        async with httpx.AsyncClient() as client:
            all_results = []
            next_cursor = None

            while True:
                params = {"location": "new"}
                if next_cursor:
                    params["pageCursor"] = next_cursor

                response = await client.get(
                    f"{self.base_url}/list/",
                    headers=self.headers,
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()

                data = response.json()
                all_results.extend(data.get("results", []))

                next_cursor = data.get("nextPageCursor")
                if not next_cursor:
                    break

            # Cache the results
            list_cache[cache_key] = all_results
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
            return document_cache[doc_id]

        # Fetch from API
        async with httpx.AsyncClient() as client:
            params = {"id": doc_id, "withHtmlContent": "true"}

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
                return None

            document = results[0]

            # Cache the document
            document_cache[doc_id] = document
            return document

    async def update_reading_progress(self, doc_id: str, progress: float):
        """
        Update reading progress for a document (fire-and-forget).

        Args:
            doc_id: Document ID
            progress: Reading progress (0.0 to 1.0)
        """
        try:
            async with httpx.AsyncClient() as client:
                await client.patch(
                    f"{self.base_url}/update/{doc_id}/",
                    headers=self.headers,
                    json={"reading_progress": progress},
                    timeout=10.0,
                )
        except Exception as e:
            # Log error but don't raise (fire-and-forget)
            print(f"Error updating reading progress for {doc_id}: {e}")

    async def archive_document(self, doc_id: str):
        """
        Archive a document and invalidate caches.

        Args:
            doc_id: Document ID
        """
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.base_url}/update/{doc_id}/",
                headers=self.headers,
                json={"location": "archive"},
                timeout=10.0,
            )
            response.raise_for_status()

        # Invalidate caches
        if doc_id in document_cache:
            del document_cache[doc_id]

        list_cache.clear()

    def invalidate_document_cache(self, doc_id: str):
        """Invalidate cached document."""
        if doc_id in document_cache:
            del document_cache[doc_id]

    def invalidate_list_cache(self):
        """Invalidate cached inbox list."""
        list_cache.clear()


# Singleton instance
client = ReadwiseClient()
