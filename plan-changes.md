I did more investigation into my current container setup. Please make the following changes. Since you're not integrating the app into my container, write integration instructions based on the changes below and whatever actually gets implemented.


The plan should use FastAPI with uvicorn, not Flask with flup. Here are the specific changes:

## Changes to Implementation Plan

### Framework and Dependencies

Replace the Flask/flup stack with:

```
fastapi
uvicorn
httpx              # async HTTP client for Readwise API
jinja2             # templates (FastAPI supports this directly)
beautifulsoup4
bleach
cachetools
python-dotenv
```

Drop `flup6`, `Flask`, and `requests`. Use `httpx` instead of `requests` since you’re in an async context anyway — this also simplifies the fire-and-forget progress updates (use `asyncio.create_task()` with an async HTTP call instead of spawning threads).

### App Structure

The plan’s structure is fine, but rename entry points:

```
readwise-kindle-web/
├── app/
│   ├── __init__.py           # empty or minimal
│   ├── main.py               # FastAPI app instance and routes
│   ├── config.py
│   ├── api_client.py         # async with httpx
│   ├── paginator.py
│   ├── sanitizer.py
│   └── templates/
│       ├── list.html
│       └── page.html
└── requirements.txt
```

You don’t need `wsgi.py` or `run_dev.py` — uvicorn handles both dev and prod.

### Async API Client

The fire-and-forget pattern becomes cleaner:

```python
async def update_reading_progress(doc_id: str, progress: float):
    async with httpx.AsyncClient() as client:
        await client.patch(...)

# In route handler:
asyncio.create_task(update_reading_progress(doc_id, progress))
```

No threads needed. The task runs in the background and you don’t await it.

### Routes

FastAPI equivalent of the planned routes:

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def list_inbox(request: Request): ...

@app.get("/read/{doc_id}", response_class=RedirectResponse)
async def read_redirect(doc_id: str): ...

@app.get("/read/{doc_id}/{page_num}", response_class=HTMLResponse)
async def read_page(request: Request, doc_id: str, page_num: int): ...

@app.post("/archive/{doc_id}", response_class=RedirectResponse)
async def archive(doc_id: str): ...
```

### Container Integration

Following your existing pattern:

**Dockerfile** — add to your existing `uv pip install`:

```
beautifulsoup4 bleach cachetools
```

(httpx, jinja2, fastapi, uvicorn are likely already installed for the consent app)

**supervisord.conf**:

```ini
[program:kindle-reader]
command=uvicorn app.main:app --host 127.0.0.1 --port 9002
directory=/usr/local/bin/kindle-reader
autostart=true
autorestart=true
```

**nginx.conf**:

```nginx
location /kindle/ {
    proxy_pass http://127.0.0.1:9002/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
}
```

### Environment

Add to your `.env`:

```
READWISE_API_TOKEN=xxx
KINDLE_PAGE_CHAR_BUDGET=1800
```

The config module reads these via `os.getenv()` or pydantic’s `BaseSettings` if you want validation.

-----

That’s the delta. The core logic (sanitizer, paginator, caching strategy) stays the same — it’s just the HTTP layer and async patterns that change to fit your existing stack.​​​​​​​​​​​​​​​​
