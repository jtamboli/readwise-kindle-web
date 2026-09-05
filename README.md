# Readwise Kindle Web Reader

A FastAPI-based web application that fetches articles from Readwise Reader API and displays them in a Kindle-friendly format with tap-zone navigation.

## Features

- **Kindle-optimized display**: Minimal CSS with tap-zone navigation, optimized for e-ink displays
- **Tap-to-scroll navigation**: Tap left/right zones to scroll through articles smoothly
- **Reading progress tracking**: Automatically updates your progress in Readwise
- **Two-tier caching**: Fast page loads with intelligent cache management
- **Archive support**: Mark articles as read directly from the Kindle

## Project Structure

```
readwise-kindle-web/
├── app/
│   ├── __init__.py           # Package initialization
│   ├── main.py               # FastAPI app and routes
│   ├── config.py             # Configuration management
│   ├── api_client.py         # Async Readwise API client
│   ├── sanitizer.py          # HTML sanitization
│   └── templates/
│       ├── list.html         # Inbox list view
│       └── page.html         # Article page view
├── requirements.txt          # Python dependencies
├── .env.example              # Example environment variables
└── README.md                 # This file
```

## Setup

### 1. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and add your Readwise API token:

```bash
cp .env.example .env
```

Edit `.env` and set your API token (get it from https://readwise.io/access_token):

```bash
KINDLE_READWISE_API_TOKEN=your_actual_token_here
KINDLE_CACHE_LIST_TTL=300
```

### 4. Run the development server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at `http://localhost:8000`

## Usage

1. Navigate to `http://localhost:8000` to see your Readwise inbox
2. Click on any article to start reading
3. Tap left/right zones on your Kindle to scroll through the article
4. Click "Archive" to mark an article as read
5. Click "Back to list" to return to the inbox

## Configuration

All configuration is done via environment variables:

- `KINDLE_READWISE_API_TOKEN` (required): Your Readwise API token
- `KINDLE_READWISE_MOBILE_SESSION` (optional): `mobilesession` header captured from the official Reader iOS app. When set, reading position is pushed to Readwise so other devices pick it up. See [Reading Progress](#reading-progress).
- `KINDLE_CACHE_LIST_TTL` (default: 300): List cache duration in seconds

## Container Integration

To integrate with your existing container infrastructure:

### Dockerfile

Add to your existing `uv pip install` command:

```dockerfile
RUN uv pip install beautifulsoup4 bleach cachetools
```

*Note: fastapi, uvicorn, httpx, and jinja2 are assumed to already be installed.*

### supervisord.conf

Add a new program section:

```ini
[program:kindle-reader]
command=uvicorn app.main:app --host 127.0.0.1 --port 9002
directory=/usr/local/bin/kindle-reader
autostart=true
autorestart=true
stdout_logfile=/var/log/kindle-reader.log
stderr_logfile=/var/log/kindle-reader.err.log
```

### nginx.conf

Add a location block to proxy requests:

```nginx
location /kindle/ {
    proxy_pass http://127.0.0.1:9002/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

The app will be accessible at `http://your-domain/kindle/`

## API Routes

- `GET /` - List inbox items
- `GET /read/{doc_id}` - Display article with tap-zone navigation
- `POST /archive/{doc_id}` - Archive document
- `GET /health` - Health check endpoint

## How It Works

### Caching Strategy

**Two-tier caching** for optimal performance:

1. **List cache**: Inbox items cached for 5 minutes (configurable)
2. **Document cache**: Full articles cached indefinitely until archived

This ensures fast page loads while keeping the inbox reasonably up-to-date.

### Navigation

Articles are displayed as a single scrollable page with **tap-zone navigation**. Tap on the left or right zones of your Kindle screen to smoothly scroll through the content without jarring page breaks.

### Reading Progress

The page beacons its scroll depth to `/kindle/progress/{id}` as you read. The exact position (block + offset) is kept in the device's `localStorage`, and the percentage is cached server-side so the list shows it immediately.

The public Readwise API can read `reading_progress` but not write it, so by default position stays on the device. Set `KINDLE_READWISE_MOBILE_SESSION` to also push it to Readwise through the private state-sync API the official apps use (documented in `docs/readwise-private-state-api.md`). Each beacon then sends two events: the current scroll depth, and a forward-only update to the reading high-water mark that the public API exposes as `reading_progress`. Only the depth percentage is written; the apps' element-based position, which indexes their own DOM, is left untouched.

Pushes are **fire-and-forget** async tasks using `asyncio.create_task()`:

- Page loads aren't blocked waiting for API updates
- Progress updates happen in the background
- If an update fails, it's logged and doesn't affect your reading experience
- A `401` means the captured session has expired; capture a fresh one from the app

### HTML Sanitization

All HTML is sanitized to only allow safe, Kindle-compatible tags:
- Text: `p`, `h1-h6`, `em`, `strong`, `blockquote`
- Lists: `ul`, `ol`, `li`
- Media: `img`, `a`
- Formatting: `br`

All inline styles, scripts, and other potentially problematic markup is stripped.

## Troubleshooting

### "KINDLE_READWISE_API_TOKEN environment variable is required"

Make sure you've created a `.env` file with your API token. The config module validates this on startup.

### Slow page loads

The first load of each article will be slower as it fetches from Readwise API. Subsequent access uses cached data and should be instant.

### Images not displaying

Check that your Kindle has network access and can load external images. Some Kindles may have restrictions on image loading.

## Development

To run in development mode with auto-reload:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## License

This is a personal project. Use at your own discretion.
