# Kindle Readwise Web Reader (Go)

A Go rewrite of the Readwise Kindle web reader application.

## Features

- Display articles from Readwise Reader API
- Kindle-optimized reading experience with tap-zone navigation
- Dark mode based on sunrise/sunset times
- Reading progress tracking
- Article archiving
- Tag-based filtering
- Random article selection

## Requirements

- Go 1.21 or later
- Readwise API token

## Configuration

Set the following environment variables:

```bash
# Required
READWISE_API_TOKEN=your_token_here

# Optional
CACHE_LIST_TTL=300              # List cache TTL in seconds (default: 300)
KINDLE_READWISE_VERBOSE=false   # Enable verbose logging (default: false)
PORT=8000                       # Server port (default: 8000)
HOST=0.0.0.0                    # Server host (default: 0.0.0.0)
TEMPLATES_DIR=templates         # Templates directory (default: templates)
```

You can also create a `.env` file in the working directory.

## Building

```bash
go build -o kindle-reader ./cmd/server/
```

## Running

```bash
./kindle-reader
```

Or with Docker:

```bash
docker build -t kindle-reader .
docker run -p 8000:8000 -e READWISE_API_TOKEN=your_token kindle-reader
```

## Routes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Home page with Shortlist and Later sections |
| GET | `/read/{doc_id}` | View full article |
| GET | `/progress/{doc_id}` | Update reading progress (beacon) |
| POST | `/archive/{doc_id}` | Archive article |
| GET | `/list/{location}` | View articles by location |
| GET | `/feed` | View feed items |
| GET | `/random` | View 10 random articles |
| GET | `/tags` | View all tags |
| GET | `/tags/{tag_name}` | View articles by tag |
| GET | `/hide/{doc_id}` | Toggle article visibility |
| GET | `/refresh` | Clear caches |
| GET | `/health` | Health check |

All routes are also available under the `/kindle` prefix.
