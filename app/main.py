"""FastAPI application for Readwise Kindle web reader."""
import random
from urllib.parse import urlparse
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from kindle_reader.api_client import client, VALID_LOCATIONS
from kindle_reader.filters import (
    KINDLE_HIDDEN_TAG,
    SORT_OPTIONS,
    DEFAULT_SORT,
    filter_hidden_articles,
    filter_seen_articles,
    sort_items,
    get_article_tags,
    filter_by_tag,
)
from kindle_reader.sanitizer import sanitize_html
from kindle_reader.sun_times import is_dark_mode
from kindle_reader.utils import deduplicate_by_id, normalize_tags

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


def extract_domain(url: str) -> str:
    """
    Extract the domain from a URL, removing 'www.' prefix if present.

    Args:
        url: Full URL string

    Returns:
        Domain name without protocol and 'www.' prefix, or empty string if invalid
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        # Remove 'www.' prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


# Register custom Jinja2 filters
templates.env.filters["words_to_minutes"] = words_to_minutes
templates.env.filters["extract_domain"] = extract_domain


@app.get("/", response_class=HTMLResponse)
async def list_home(request: Request):
    """
    Display home page with Shortlist and Later sections.

    Returns:
        HTML page with combined article lists
    """
    try:
        is_dark = is_dark_mode()
        sort_order = request.cookies.get("sort_order", DEFAULT_SORT)

        shortlist_items = await client.get_items_by_location("shortlist", limit=5)
        later_items = await client.get_items_by_location("later", limit=20)

        # Filter out hidden articles
        shortlist_items = filter_hidden_articles(shortlist_items)
        later_items = filter_hidden_articles(later_items)

        # Sort by user preference
        shortlist_items = sort_items(shortlist_items, sort_order)
        later_items = sort_items(later_items, sort_order)

        return templates.TemplateResponse(
            "list.html",
            {
                "request": request,
                "shortlist_items": shortlist_items,
                "later_items": later_items,
                "is_dark": is_dark,
                "sort_order": sort_order,
                "sort_options": SORT_OPTIONS,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching items: {str(e)}")


def get_back_url(from_list: str) -> str:
    """
    Get the back URL based on the source list.

    Args:
        from_list: Source list identifier (e.g., 'feed', 'later', 'shortlist', 'random')

    Returns:
        URL to navigate back to the source list
    """
    if not from_list:
        return "/kindle/"

    from_list = from_list.lower()

    if from_list == "feed":
        return "/kindle/feed"
    elif from_list == "random":
        return "/kindle/random"
    elif from_list in ("later", "shortlist", "new", "archive"):
        return f"/kindle/list/{from_list}"
    elif from_list.startswith("tag/"):
        tag_name = from_list[4:]  # Remove 'tag/' prefix
        return f"/kindle/tags/{tag_name}"
    else:
        return "/kindle/"


@app.get("/read/{doc_id}", response_class=HTMLResponse)
async def read_article(
    request: Request,
    doc_id: str,
    next: str = None,
):
    """
    Display a full article with JS tap-zone scrolling.

    Args:
        doc_id: Document ID
        next: Optional next document ID for navigation

    Returns:
        HTML page with full article content
    """
    try:
        # Get navigation context from query params
        from_list = request.query_params.get("from", "")

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

        # Compute navigation URLs
        back_url = get_back_url(from_list)
        is_feed = from_list.lower() == "feed" if from_list else False

        # Build next article URL if available
        next_url = None
        if next:
            next_url = f"/kindle/read/{next}?from={from_list}"

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
                "back_url": back_url,
                "is_feed": is_feed,
                "next_url": next_url,
                "from_list": from_list,
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
    client.update_reading_progress(doc_id, progress)
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


@app.post("/archive-next/{doc_id}", response_class=RedirectResponse)
async def archive_and_next(request: Request, doc_id: str):
    """
    Archive a document and navigate to the next one.

    Args:
        doc_id: Document ID to archive
        request: Request object to get query params (next, from)

    Returns:
        Redirect to next article or back to list if no next
    """
    try:
        await client.archive_document(doc_id)

        # Get next article URL from query params
        next_doc_id = request.query_params.get("next", "")
        from_list = request.query_params.get("from", "")

        if next_doc_id:
            # Redirect to next article with context
            return RedirectResponse(
                url=f"/kindle/read/{next_doc_id}?from={from_list}",
                status_code=303
            )
        else:
            # No next article, go back to list
            return RedirectResponse(url=get_back_url(from_list), status_code=303)
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
        sort_order = request.cookies.get("sort_order", DEFAULT_SORT)
        items = await client.get_items_by_location(location, limit=100)

        # Filter out hidden articles
        items = filter_hidden_articles(items)

        # Filter out seen articles in Feed view
        if location == "feed":
            items = filter_seen_articles(items)

        # Sort by user preference
        items = sort_items(items, sort_order)

        # Capitalize location for display
        display_name = location.capitalize()

        return templates.TemplateResponse(
            "list_single.html",
            {
                "request": request,
                "items": items,
                "list_name": display_name,
                "is_dark": is_dark,
                "sort_order": sort_order,
                "sort_options": SORT_OPTIONS,
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
        sort_order = request.cookies.get("sort_order", DEFAULT_SORT)
        items = await client.get_items_by_location("feed", limit=100)

        # Filter out hidden articles
        items = filter_hidden_articles(items)

        # Filter out seen articles
        items = filter_seen_articles(items)

        # Sort by user preference
        items = sort_items(items, sort_order)

        return templates.TemplateResponse(
            "list_single.html",
            {
                "request": request,
                "items": items,
                "list_name": "Feed",
                "is_dark": is_dark,
                "sort_order": sort_order,
                "sort_options": SORT_OPTIONS,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching feed items: {str(e)}")


@app.get("/random", response_class=HTMLResponse)
async def list_random(request: Request):
    """
    Display 10 random articles from Later and Shortlist locations.

    Articles hidden on Kindle are excluded.
    Results are shuffled in random order.

    Returns:
        HTML page with random article list
    """
    try:
        is_dark = is_dark_mode()
        sort_order = request.cookies.get("sort_order", DEFAULT_SORT)

        # Fetch articles from both later and shortlist
        later_items = await client.get_items_by_location("later", limit=100)
        shortlist_items = await client.get_items_by_location("shortlist", limit=100)

        # Combine all articles
        all_items = later_items + shortlist_items

        # Filter out hidden articles
        all_items = filter_hidden_articles(all_items)

        # Remove duplicates by ID (in case an article appears in both locations)
        unique_items = deduplicate_by_id(all_items)

        # Shuffle the articles
        random.shuffle(unique_items)

        # Take the first 10 articles
        random_items = unique_items[:10]

        return templates.TemplateResponse(
            "list_single.html",
            {
                "request": request,
                "items": random_items,
                "list_name": "Random",
                "is_dark": is_dark,
                "sort_order": sort_order,
                "sort_options": SORT_OPTIONS,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching random articles: {str(e)}")


@app.get("/tags", response_class=HTMLResponse)
async def list_tags(request: Request):
    """
    Display list of all tags sorted by article count.

    Returns:
        HTML page with tag list
    """
    try:
        is_dark = is_dark_mode()
        sort_order = request.cookies.get("sort_order", DEFAULT_SORT)

        # Get library articles to extract tags
        all_articles = await client.get_library_articles(limit_per_location=100)

        # Count tags using the shared utility
        tag_counts = {}
        for article in all_articles:
            for tag_name in get_article_tags(article):
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
                "sort_order": sort_order,
                "sort_options": SORT_OPTIONS,
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
        sort_order = request.cookies.get("sort_order", DEFAULT_SORT)

        # Get library articles and filter by tag using shared utility
        all_articles = await client.get_library_articles(limit_per_location=100)

        # Filter articles that have the specified tag
        filtered_items = filter_by_tag(all_articles, tag_name)

        # Filter out hidden articles
        filtered_items = filter_hidden_articles(filtered_items)

        # Sort by user preference
        filtered_items = sort_items(filtered_items, sort_order)

        return templates.TemplateResponse(
            "list_single.html",
            {
                "request": request,
                "items": filtered_items,
                "list_name": f"Tag: {tag_name}",
                "is_dark": is_dark,
                "sort_order": sort_order,
                "sort_options": SORT_OPTIONS,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching articles for tag '{tag_name}': {str(e)}")


@app.get("/hide/{doc_id}", response_class=RedirectResponse)
async def toggle_hidden(request: Request, doc_id: str):
    """
    Toggle the hidden status of an article by adding/removing the 'kindle-hidden' tag.

    Args:
        doc_id: Document ID to toggle
        request: FastAPI request object (used to get referer)

    Returns:
        Redirect to the referring page or home
    """
    try:
        # Toggle the kindle-hidden tag
        is_now_hidden = await client.toggle_tag(doc_id, KINDLE_HIDDEN_TAG)

        # Cache is already invalidated by toggle_tag method

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
