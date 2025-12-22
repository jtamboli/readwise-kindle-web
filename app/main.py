"""FastAPI application for Readwise Kindle web reader."""
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from kindle_reader.api_client import client, VALID_LOCATIONS
from kindle_reader.sanitizer import sanitize_html
from kindle_reader.sun_times import is_dark_mode

# 1x1 transparent GIF for progress tracking beacon
TRANSPARENT_GIF = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'

app = FastAPI(title="Readwise Kindle Web Reader")
templates = Jinja2Templates(directory="/app/kindle_reader/templates")


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


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
