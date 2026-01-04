"""FastAPI application for Readwise Kindle web reader."""
import asyncio
from typing import List, Dict
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from kindle_reader.api_client import client, VALID_LOCATIONS
from kindle_reader.sanitizer import sanitize_html
from kindle_reader.sun_times import is_dark_mode
from kindle_reader.hidden_storage import hidden_storage

# 1x1 transparent GIF for progress tracking beacon
TRANSPARENT_GIF = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'

app = FastAPI(title="Readwise Kindle Web Reader")
templates = Jinja2Templates(directory="/app/kindle_reader/templates")


def words_to_minutes(word_count: int) -> int:
    """
    Convert word count to estimated reading time in minutes.

    Uses an average reading speed of 238 words per minute.
    Rounds up to ensure at least 1 minute for any content.

    Args:
        word_count: Number of words in the document

    Returns:
        Estimated reading time in minutes (minimum 1)
    """
    if not word_count or word_count <= 0:
        return 0
    # Average reading speed: 238 words per minute
    minutes = (word_count + 237) // 238  # Round up using integer division
    return max(1, minutes)


# Register custom Jinja2 filter
templates.env.filters["words_to_minutes"] = words_to_minutes


def filter_hidden_articles(items: List[Dict]) -> List[Dict]:
    """
    Filter out articles that are marked as hidden from Kindle.

    Args:
        items: List of document dictionaries

    Returns:
        List of documents with hidden articles removed
    """
    return [item for item in items if not hidden_storage.is_hidden(item.get("id"))]


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
    def sort_key(item):
        # Use last_opened_at if available, otherwise fall back to last_moved_at
        return item.get("last_opened_at") or item.get("last_moved_at", "")

    return sorted(items, key=sort_key, reverse=True)


@app.get("/", response_class=HTMLResponse)
async def list_home(request: Request):
    """
    Display home page with Shortlist and Later sections.

    Returns:
        HTML page with combined article lists
    """
    try:
        is_dark = is_dark_mode()
        shortlist_items = await client.get_items_by_location("shortlist", limit=5)
        later_items = await client.get_items_by_location("later", limit=20)

        # Filter out hidden articles
        shortlist_items = filter_hidden_articles(shortlist_items)
        later_items = filter_hidden_articles(later_items)

        # Sort by recent activity (last_opened_at with fallback to last_moved_at)
        shortlist_items = sort_by_recent_activity(shortlist_items)
        later_items = sort_by_recent_activity(later_items)

        return templates.TemplateResponse(
            "list.html",
            {
                "request": request,
                "shortlist_items": shortlist_items,
                "later_items": later_items,
                "is_dark": is_dark,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching items: {str(e)}")


@app.get("/read/{doc_id}", response_class=HTMLResponse)
async def read_article(request: Request, doc_id: str):
    """
    Display a full article with JS tap-zone scrolling.

    Args:
        doc_id: Document ID

    Returns:
        HTML page with full article content
    """
    try:
        # Fetch document
        document = await client.get_document(doc_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get HTML content
        html_content = document.get("html_content")
        if not html_content:
            raise HTTPException(status_code=404, detail="Document has no content")

        # Sanitize HTML
        clean_html = sanitize_html(html_content)

        # Render page
        is_dark = is_dark_mode()
        reading_progress = document.get("reading_progress", 0) or 0
        return templates.TemplateResponse(
            "page.html",
            {
                "request": request,
                "doc_id": doc_id,
                "title": document.get("title", "Untitled"),
                "author": document.get("author"),
                "source": document.get("source"),
                "content": clean_html,
                "is_dark": is_dark,
                "reading_progress": reading_progress,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rendering article: {str(e)}")


@app.get("/progress/{doc_id}")
async def update_progress(doc_id: str, p: float = 0):
    """
    Update reading progress via JS beacon.

    Args:
        doc_id: Document ID
        p: Progress as float 0-1

    Returns:
        1x1 transparent GIF
    """
    progress = min(1.0, max(0.0, p))
    asyncio.create_task(client.update_reading_progress(doc_id, progress))
    return Response(content=TRANSPARENT_GIF, media_type="image/gif")


@app.post("/archive/{doc_id}", response_class=RedirectResponse)
async def archive(doc_id: str):
    """
    Archive a document.

    Args:
        doc_id: Document ID

    Returns:
        Redirect to inbox list
    """
    try:
        await client.archive_document(doc_id)
        return RedirectResponse(url="/kindle/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error archiving document: {str(e)}")


@app.get("/list/{location}", response_class=HTMLResponse)
async def list_by_location(request: Request, location: str):
    """
    Display list of items from a specific location.

    Args:
        location: One of 'shortlist', 'later', 'new', 'archive', 'feed'

    Returns:
        HTML page with article list
    """
    if location not in VALID_LOCATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid location: {location}. Must be one of {', '.join(sorted(VALID_LOCATIONS))}"
        )

    try:
        is_dark = is_dark_mode()
        items = await client.get_items_by_location(location, limit=100)

        # Filter out hidden articles
        items = filter_hidden_articles(items)

        # Sort by recent activity (last_opened_at with fallback to last_moved_at)
        items = sort_by_recent_activity(items)

        # Capitalize location for display
        display_name = location.capitalize()

        return templates.TemplateResponse(
            "list_single.html",
            {
                "request": request,
                "items": items,
                "list_name": display_name,
                "is_dark": is_dark,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching {location} items: {str(e)}")


@app.get("/feed", response_class=HTMLResponse)
async def list_feed(request: Request):
    """
    Display list of feed items.

    Returns:
        HTML page with feed article list
    """
    try:
        is_dark = is_dark_mode()
        items = await client.get_items_by_location("feed", limit=100)

        # Filter out hidden articles
        items = filter_hidden_articles(items)

        # Sort by recent activity (last_opened_at with fallback to last_moved_at)
        items = sort_by_recent_activity(items)

        return templates.TemplateResponse(
            "list_single.html",
            {
                "request": request,
                "items": items,
                "list_name": "Feed",
                "is_dark": is_dark,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching feed items: {str(e)}")


@app.get("/tags", response_class=HTMLResponse)
async def list_tags(request: Request):
    """
    Display list of all tags sorted by article count.

    Returns:
        HTML page with tag list
    """
    try:
        is_dark = is_dark_mode()

        # Get library articles to extract tags
        all_articles = await client.get_library_articles(limit_per_location=100)

        # Count tags
        tag_counts = {}
        for article in all_articles:
            article_tags = article.get("tags", {})
            # Tags can be a dict with tag names as keys or a list
            if isinstance(article_tags, dict):
                tag_names = list(article_tags.keys())
            elif isinstance(article_tags, list):
                tag_names = article_tags
            else:
                tag_names = []

            for tag_name in tag_names:
                if tag_name:  # Skip empty tags
                    tag_counts[tag_name] = tag_counts.get(tag_name, 0) + 1

        # Convert to list of dicts and sort by count (descending)
        tags = [{"name": name, "count": count} for name, count in tag_counts.items()]
        tags.sort(key=lambda x: x["count"], reverse=True)

        return templates.TemplateResponse(
            "tags.html",
            {
                "request": request,
                "tags": tags,
                "is_dark": is_dark,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tags: {str(e)}")


@app.get("/tags/{tag_name}", response_class=HTMLResponse)
async def list_articles_by_tag(request: Request, tag_name: str):
    """
    Display list of articles with a specific tag.

    Args:
        tag_name: Name of the tag to filter by

    Returns:
        HTML page with filtered article list
    """
    try:
        is_dark = is_dark_mode()

        # Get library articles and filter by tag
        all_articles = await client.get_library_articles(limit_per_location=100)

        # Filter articles that have the specified tag
        filtered_items = []
        for article in all_articles:
            article_tags = article.get("tags", {})
            # Tags can be a dict with tag names as keys or a list
            if isinstance(article_tags, dict):
                tag_names = list(article_tags.keys())
            elif isinstance(article_tags, list):
                tag_names = article_tags
            else:
                tag_names = []

            if tag_name in tag_names:
                filtered_items.append(article)

        # Filter out hidden articles
        filtered_items = filter_hidden_articles(filtered_items)

        # Sort by recent activity
        filtered_items = sort_by_recent_activity(filtered_items)

        return templates.TemplateResponse(
            "list_single.html",
            {
                "request": request,
                "items": filtered_items,
                "list_name": f"Tag: {tag_name}",
                "is_dark": is_dark,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching articles for tag '{tag_name}': {str(e)}")


@app.get("/hide/{doc_id}", response_class=RedirectResponse)
async def toggle_hidden(request: Request, doc_id: str):
    """
    Toggle the hidden status of an article.

    Args:
        doc_id: Document ID to toggle
        request: FastAPI request object (used to get referer)

    Returns:
        Redirect to the referring page or home
    """
    try:
        # Toggle the hidden status
        is_now_hidden = hidden_storage.toggle(doc_id)

        # Invalidate list cache to ensure fresh data on next load
        client.invalidate_list_cache()

        # Redirect back to the referring page or home
        referer = request.headers.get("referer")
        if referer and "/kindle/" in referer:
            return RedirectResponse(url=referer, status_code=303)
        else:
            return RedirectResponse(url="/kindle/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error toggling hidden status: {str(e)}")


@app.get("/refresh", response_class=RedirectResponse)
async def refresh_cache():
    """
    Clear all caches and redirect to home page.

    Returns:
        Redirect to home page
    """
    client.invalidate_list_cache()
    return RedirectResponse(url="/kindle/", status_code=303)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
