"""FastAPI application for Readwise Kindle web reader."""
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api_client import client
from app.sanitizer import sanitize_html
from app.paginator import paginate_html

app = FastAPI(title="Readwise Kindle Web Reader")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def list_inbox(request: Request):
    """
    Display list of inbox items.

    Returns:
        HTML page with inbox article list
    """
    try:
        items = await client.get_inbox_items()
        return templates.TemplateResponse(
            "list.html",
            {"request": request, "items": items},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching inbox: {str(e)}")


@app.get("/read/{doc_id}", response_class=RedirectResponse)
async def read_redirect(doc_id: str):
    """
    Redirect to first page of document.

    Args:
        doc_id: Document ID

    Returns:
        Redirect to page 1
    """
    return RedirectResponse(url=f"/read/{doc_id}/1", status_code=302)


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
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error archiving document: {str(e)}")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
