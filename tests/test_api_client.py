"""Tests for Readwise API client."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

# Patch Config.validate to avoid token validation during import
with patch.dict('os.environ', {'KINDLE_READWISE_API_TOKEN': 'test-token'}):
    from kindle_reader.api_client import (
        ReadwiseClient,
        VALID_LOCATIONS,
        STATE_SCHEMA_VERSION,
        ULID_ALPHABET,
        build_position_events,
        list_cache,
        document_cache,
        new_ulid,
        position_sync_warning,
    )
    import kindle_reader.api_client as api_client_module
    from kindle_reader.config import Config


@pytest.fixture
def client():
    """Create a fresh ReadwiseClient instance."""
    return ReadwiseClient()


@pytest.fixture
def mock_response():
    """Create a mock HTTP response."""
    def _create_response(json_data, status_code=200):
        response = MagicMock(spec=httpx.Response)
        response.json.return_value = json_data
        response.status_code = status_code
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Error", request=MagicMock(), response=response
            )
        return response
    return _create_response


@pytest.fixture(autouse=True)
def reset_sync_status():
    """Start each test with the state-sync session not rejected."""
    api_client_module._session_rejected = False
    yield
    api_client_module._session_rejected = False


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear caches before each test."""
    list_cache.clear()
    document_cache.clear()
    yield
    list_cache.clear()
    document_cache.clear()


class TestValidLocations:
    """Tests for VALID_LOCATIONS constant."""

    def test_contains_expected_locations(self):
        """Should contain all expected location values."""
        expected = {"new", "later", "shortlist", "archive", "feed"}
        assert VALID_LOCATIONS == expected


class TestGetItemsByLocation:
    """Tests for get_items_by_location method."""

    @pytest.mark.asyncio
    async def test_fetches_items_from_api(self, client, mock_response):
        """Should fetch items from the Readwise API."""
        response_data = {
            "results": [
                {"id": "1", "title": "Article 1"},
                {"id": "2", "title": "Article 2"},
            ],
            "nextPageCursor": None,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.get.return_value = mock_response(response_data)

            result = await client.get_items_by_location("later", limit=10)

            assert len(result) == 2
            assert result[0]["id"] == "1"
            assert result[1]["id"] == "2"

    @pytest.mark.asyncio
    async def test_caches_results(self, client, mock_response):
        """Should cache results after first fetch."""
        response_data = {
            "results": [{"id": "1", "title": "Article 1"}],
            "nextPageCursor": None,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.get.return_value = mock_response(response_data)

            # First call - should hit API
            result1 = await client.get_items_by_location("later", limit=10)
            # Second call - should use cache
            result2 = await client.get_items_by_location("later", limit=10)

            # API should only be called once
            assert mock_async_client.get.call_count == 1
            assert result1 == result2

    @pytest.mark.asyncio
    async def test_invalid_location_raises_error(self, client):
        """Should raise ValueError for invalid location."""
        with pytest.raises(ValueError) as exc_info:
            await client.get_items_by_location("invalid", limit=10)
        assert "Invalid location" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handles_pagination(self, client, mock_response):
        """Should handle paginated responses."""
        page1_data = {
            "results": [{"id": "1"}],
            "nextPageCursor": "cursor123",
        }
        page2_data = {
            "results": [{"id": "2"}],
            "nextPageCursor": None,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.get.side_effect = [
                mock_response(page1_data),
                mock_response(page2_data),
            ]

            result = await client.get_items_by_location("later", limit=10)

            assert len(result) == 2
            assert mock_async_client.get.call_count == 2


class TestGetDocument:
    """Tests for get_document method."""

    @pytest.mark.asyncio
    async def test_fetches_document_from_api(self, client, mock_response):
        """Should fetch document with HTML content."""
        response_data = {
            "results": [
                {
                    "id": "doc-1",
                    "title": "Test Document",
                    "html_content": "<p>Content</p>",
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.get.return_value = mock_response(response_data)

            result = await client.get_document("doc-1")

            assert result["id"] == "doc-1"
            assert result["title"] == "Test Document"
            assert result["html_content"] == "<p>Content</p>"

    @pytest.mark.asyncio
    async def test_caches_document(self, client, mock_response):
        """Should cache document after first fetch."""
        response_data = {
            "results": [{"id": "doc-1", "title": "Test"}]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.get.return_value = mock_response(response_data)

            # First call
            await client.get_document("doc-1")
            # Second call - should use cache
            await client.get_document("doc-1")

            assert mock_async_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_returns_none_for_not_found(self, client, mock_response):
        """Should return None when document not found."""
        response_data = {"results": []}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.get.return_value = mock_response(response_data)

            result = await client.get_document("nonexistent")

            assert result is None


class TestMarkDocumentSeen:
    """Tests for mark_document_seen method."""

    @pytest.mark.asyncio
    async def test_patches_seen_true(self, client, mock_response):
        """Should PATCH the update endpoint with seen=true."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.patch.return_value = mock_response({})

            await client.mark_document_seen("doc-1")

            call_args = mock_async_client.patch.call_args
            assert "update/doc-1/" in call_args[0][0]
            assert call_args[1]["json"] == {"seen": True}

    @pytest.mark.asyncio
    async def test_stamps_open_timestamps_in_list_cache(self, client, mock_response):
        """Should stamp cached list entries so the item leaves the Feed."""
        list_cache["list_feed_100"] = [
            {"id": "doc-1", "first_opened_at": None, "last_opened_at": None},
            {"id": "doc-2", "first_opened_at": None, "last_opened_at": None},
        ]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.patch.return_value = mock_response({})

            await client.mark_document_seen("doc-1")

        cached = {item["id"]: item for item in list_cache["list_feed_100"]}
        assert cached["doc-1"]["first_opened_at"] is not None
        assert cached["doc-1"]["last_opened_at"] is not None
        assert cached["doc-2"]["last_opened_at"] is None

    @pytest.mark.asyncio
    async def test_preserves_existing_first_opened_at(self, client, mock_response):
        """Should refresh last_opened_at but keep the original first open."""
        document_cache["doc-1"] = {
            "id": "doc-1",
            "first_opened_at": "2024-01-01T00:00:00+00:00",
            "last_opened_at": "2024-01-01T00:00:00+00:00",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.patch.return_value = mock_response({})

            await client.mark_document_seen("doc-1")

        assert document_cache["doc-1"]["first_opened_at"] == "2024-01-01T00:00:00+00:00"
        assert document_cache["doc-1"]["last_opened_at"] != "2024-01-01T00:00:00+00:00"

    @pytest.mark.asyncio
    async def test_raises_on_api_error(self, client, mock_response):
        """Should propagate API errors to the caller."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.patch.return_value = mock_response({}, status_code=500)

            with pytest.raises(httpx.HTTPStatusError):
                await client.mark_document_seen("doc-1")


class TestUpdateReadingProgress:
    """Tests for update_reading_progress method."""

    def test_updates_cached_progress(self, client):
        """Should update reading_progress on the cached document in place."""
        document_cache["doc-1"] = {"id": "doc-1", "reading_progress": 0.0}

        client.update_reading_progress("doc-1", 0.5)

        assert document_cache["doc-1"]["reading_progress"] == 0.5

    def test_noop_when_document_not_cached(self, client):
        """Should silently do nothing (no error) when the doc isn't cached."""
        assert "missing-doc" not in document_cache

        # Should not raise and should not create a cache entry.
        client.update_reading_progress("missing-doc", 0.5)

        assert "missing-doc" not in document_cache

    def test_makes_no_network_call(self, client):
        """The cache update never touches the network; syncing is a separate step."""
        document_cache["doc-1"] = {"id": "doc-1", "reading_progress": 0.0}

        with patch("httpx.AsyncClient") as mock_client_class:
            client.update_reading_progress("doc-1", 0.9)

            mock_client_class.assert_not_called()
        assert document_cache["doc-1"]["reading_progress"] == 0.9


class TestNewUlid:
    """Tests for the ULID generator used for state-sync event IDs."""

    def test_shape(self):
        """26 Crockford base32 characters, unique per call."""
        a, b = new_ulid(), new_ulid()
        assert len(a) == 26
        assert set(a) <= set(ULID_ALPHABET)
        assert a != b

    def test_sorts_by_time(self):
        """A later ULID compares greater, so the server sees events in order."""
        with patch("kindle_reader.api_client.time.time", return_value=1_000_000.0):
            earlier = new_ulid()
        with patch("kindle_reader.api_client.time.time", return_value=1_000_001.0):
            later = new_ulid()
        assert earlier < later


class TestBuildPositionEvents:
    """Tests for the state-sync events emitted on scroll."""

    def test_emits_scroll_and_high_water_events(self):
        events = build_position_events("doc-1", 0.4, timestamp_ms=1234)

        assert [e["name"] for e in events] == [
            "document-scroll-position-updated",
            "document-progress-position-updated",
        ]
        for e in events:
            assert e["timestamp"] == 1234
            assert e["userInteraction"] == {"name": "scroll"}
            assert e["dataUpdates"]["itemsUpdated"] == [{"id": "doc-1", "type": "documents"}]
            assert e["dataUpdates"]["reversePatch"] == []
            assert len(e["id"]) == 26 and len(e["correlationId"]) == 26
            assert e["environment"]["agent"]["category"] == "mobile-app"

    def test_scroll_event_replaces_current_depth(self):
        scroll, _ = build_position_events("doc-1", 0.4)

        assert scroll["dataUpdates"]["forwardPatch"] == [
            {"op": "replace", "path": "/documents/doc-1/currentScrollPosition/scrollDepth", "value": 0.4}
        ]

    def test_high_water_event_is_guarded_forward_only(self):
        _, high_water = build_position_events("doc-1", 0.4)

        assert high_water["dataUpdates"]["forwardPatch"] == [
            {"op": "test", "path": "/documents/doc-1/readingPosition/scrollDepth", "value": "<0.4"},
            {"op": "replace", "path": "/documents/doc-1/readingPosition/scrollDepth", "value": 0.4},
        ]


class TestSyncReadingPosition:
    """Tests for sync_reading_position method."""

    @pytest.mark.asyncio
    async def test_noop_without_session(self, client):
        """Without a captured session the private API is never called."""
        with patch.object(Config, "KINDLE_READWISE_MOBILE_SESSION", None), \
                patch("httpx.AsyncClient") as mock_client_class:
            await client.sync_reading_position("doc-1", 0.5)

            mock_client_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_posts_events_with_session_header(self, mock_response):
        """Should POST the event envelope to the state API using the mobile session."""
        with patch.object(Config, "KINDLE_READWISE_MOBILE_SESSION", "sess-123"):
            client = ReadwiseClient()
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_async_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_async_client
                mock_async_client.post.return_value = mock_response({})

                await client.sync_reading_position("doc-1", 0.5)

                mock_async_client.post.assert_called_once()
                args, kwargs = mock_async_client.post.call_args
                assert args[0] == "https://readwise.io/reader/api/state/update"
                assert kwargs["headers"]["mobilesession"] == "sess-123"
                assert "Authorization" not in kwargs["headers"]
                body = kwargs["json"]
                assert body["schemaVersion"] == STATE_SCHEMA_VERSION
                assert body["isChunkingSupported"] is True
                assert [e["name"] for e in body["events"]] == [
                    "document-scroll-position-updated",
                    "document-progress-position-updated",
                ]

    @pytest.mark.asyncio
    async def test_raises_on_expired_session(self, mock_response):
        """A 401 propagates so the caller can log that the session needs re-capturing."""
        with patch.object(Config, "KINDLE_READWISE_MOBILE_SESSION", "sess-123"):
            client = ReadwiseClient()
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_async_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_async_client
                mock_async_client.post.return_value = mock_response({}, status_code=401)

                with pytest.raises(httpx.HTTPStatusError):
                    await client.sync_reading_position("doc-1", 0.5)


class TestPositionSyncWarning:
    """Tests for the home-list warning about position sync."""

    def test_warns_when_session_unset(self):
        with patch.object(Config, "KINDLE_READWISE_MOBILE_SESSION", None):
            assert "KINDLE_READWISE_MOBILE_SESSION is not set" in position_sync_warning()

    def test_silent_when_session_set_and_accepted(self):
        with patch.object(Config, "KINDLE_READWISE_MOBILE_SESSION", "sess-123"):
            assert position_sync_warning() is None

    @pytest.mark.asyncio
    async def test_warns_after_401_until_next_success(self, mock_response):
        """A rejected session flags the warning; an accepted push clears it."""
        with patch.object(Config, "KINDLE_READWISE_MOBILE_SESSION", "sess-123"):
            client = ReadwiseClient()
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_async_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_async_client

                mock_async_client.post.return_value = mock_response({}, status_code=401)
                with pytest.raises(httpx.HTTPStatusError):
                    await client.sync_reading_position("doc-1", 0.5)
                assert "rejected (401)" in position_sync_warning()

                mock_async_client.post.return_value = mock_response({})
                await client.sync_reading_position("doc-1", 0.6)
                assert position_sync_warning() is None

    @pytest.mark.asyncio
    async def test_other_errors_do_not_flag_session(self, mock_response):
        """A 500 is transient, not a bad token, so no session warning."""
        with patch.object(Config, "KINDLE_READWISE_MOBILE_SESSION", "sess-123"):
            client = ReadwiseClient()
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_async_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_async_client
                mock_async_client.post.return_value = mock_response({}, status_code=500)

                with pytest.raises(httpx.HTTPStatusError):
                    await client.sync_reading_position("doc-1", 0.5)
                assert position_sync_warning() is None


class TestArchiveDocument:
    """Tests for archive_document method."""

    @pytest.mark.asyncio
    async def test_sends_archive_request(self, client, mock_response):
        """Should send PATCH request to archive."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.patch.return_value = mock_response({})

            await client.archive_document("doc-1")

            mock_async_client.patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidates_caches(self, client, mock_response):
        """Should invalidate both document and list caches."""
        # Pre-populate caches
        document_cache["doc-1"] = {"id": "doc-1"}
        list_cache["list_later_100"] = [{"id": "1"}]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.patch.return_value = mock_response({})

            await client.archive_document("doc-1")

            assert "doc-1" not in document_cache
            assert len(list_cache) == 0


class TestToggleTag:
    """Tests for toggle_tag method."""

    @pytest.mark.asyncio
    async def test_adds_tag_when_not_present(self, client, mock_response):
        """Should add tag when not already present."""
        doc_response = {
            "results": [{"id": "doc-1", "tags": {"existing": {}}}]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.get.return_value = mock_response(doc_response)
            mock_async_client.patch.return_value = mock_response({})

            result = await client.toggle_tag("doc-1", "new-tag")

            assert result is True  # Tag was added

    @pytest.mark.asyncio
    async def test_removes_tag_when_present(self, client, mock_response):
        """Should remove tag when already present."""
        doc_response = {
            "results": [{"id": "doc-1", "tags": {"existing": {}, "to-remove": {}}}]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.get.return_value = mock_response(doc_response)
            mock_async_client.patch.return_value = mock_response({})

            result = await client.toggle_tag("doc-1", "to-remove")

            assert result is False  # Tag was removed

    @pytest.mark.asyncio
    async def test_uses_provided_article_data(self, client, mock_response):
        """Should use provided article data instead of fetching."""
        article_data = {"id": "doc-1", "tags": ["existing"]}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.patch.return_value = mock_response({})

            await client.toggle_tag("doc-1", "new-tag", current_article_data=article_data)

            # GET should not be called since we provided article data
            mock_async_client.get.assert_not_called()


class TestCacheInvalidation:
    """Tests for cache invalidation methods."""

    def test_invalidate_document_cache(self, client):
        """Should remove specific document from cache."""
        document_cache["doc-1"] = {"id": "doc-1"}
        document_cache["doc-2"] = {"id": "doc-2"}

        client.invalidate_document_cache("doc-1")

        assert "doc-1" not in document_cache
        assert "doc-2" in document_cache

    def test_invalidate_list_cache(self, client):
        """Should clear all list cache entries."""
        list_cache["list_later_100"] = [{"id": "1"}]
        list_cache["list_shortlist_100"] = [{"id": "2"}]

        client.invalidate_list_cache()

        assert len(list_cache) == 0


class TestGetLibraryArticles:
    """Tests for get_library_articles method."""

    @pytest.mark.asyncio
    async def test_fetches_from_later_and_shortlist(self, client, mock_response):
        """Should fetch from both later and shortlist locations."""
        later_response = {
            "results": [{"id": "1", "title": "Later Article"}],
            "nextPageCursor": None,
        }
        shortlist_response = {
            "results": [{"id": "2", "title": "Shortlist Article"}],
            "nextPageCursor": None,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.get.side_effect = [
                mock_response(later_response),
                mock_response(shortlist_response),
            ]

            result = await client.get_library_articles(limit_per_location=100)

            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_deduplicates_articles(self, client, mock_response):
        """Should remove duplicate articles by ID."""
        later_response = {
            "results": [{"id": "1", "title": "Article"}],
            "nextPageCursor": None,
        }
        shortlist_response = {
            "results": [{"id": "1", "title": "Same Article"}],  # Duplicate
            "nextPageCursor": None,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_async_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.get.side_effect = [
                mock_response(later_response),
                mock_response(shortlist_response),
            ]

            result = await client.get_library_articles(limit_per_location=100)

            assert len(result) == 1
