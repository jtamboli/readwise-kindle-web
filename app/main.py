"""FastAPI application for Readwise Kindle web reader."""
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from kindle_reader.api_client import client, VALID_LOCATIONS
from kindle_reader.sanitizer import sanitize_html
from kindle_reader.paginator import paginate_html
from kindle_reader.sun_times import is_dark_mode

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


@app.get("/read/{doc_id}", response_class=RedirectResponse)
async def read_redirect(doc_id: str):
    """
    Redirect to first page of document.

    Args:
        doc_id: Document ID

    Returns:
        Redirect to page 1
    """
    return RedirectResponse(url=f"/kindle/read/{doc_id}/1", status_code=302)


@app.get("/read/{doc_id}/{page_num}", response_class=HTMLResponse)
async def read_page(request: Request, doc_id: str, page_num: int):
    """
    Display a single page of a document.

    Args:
        doc_id: Document ID
        page_num: Page number (1-indexed)

    Returns:
        HTML page with document content and navigation
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

        # Paginate
        pages, total_pages = paginate_html(clean_html, doc_id)

        # Validate page number
        if page_num < 1 or page_num > total_pages:
            raise HTTPException(
                status_code=404, detail=f"Page {page_num} not found (total: {total_pages})"
            )

        # Get page content (convert to 0-indexed)
        page_content = pages[page_num - 1]

        # Calculate and update reading progress (fire-and-forget)
        progress = page_num / total_pages
        asyncio.create_task(client.update_reading_progress(doc_id, progress))

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
                "content": page_content,
                "page_num": page_num,
                "total_pages": total_pages,
                "is_dark": is_dark,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rendering page: {str(e)}")


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
