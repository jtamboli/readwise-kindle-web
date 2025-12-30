That simplifies things considerably. With a fixed target device, you can empirically determine your page budget once and hardcode it.

## Design Outline

### Server

Python with Flask or FastAPI. Single-user, no auth UI needed — just configure your Readwise Reader API token as an environment variable or config file.

### Data Flow

1. Server fetches items from Readwise Reader API on demand (with reasonable caching to avoid hammering the API)
1. For article content, server parses and sanitizes HTML
1. Each article view updates reading progress via API call

### Routes

```
GET /
    List view of inbox items (title, source, maybe first line)
    Each item links to /read/<document_id>

GET /read/<document_id>
    Renders full article with tap-zone navigation
    On load, PUTs reading progress to Readwise API

POST /archive/<document_id>
    Archives the item via API
    Redirects to / (or to next unread item, your preference)
```

### Navigation

Articles are displayed as a single scrollable page with tap-zone navigation:

1. Parse HTML into block-level elements (p, h1-h6, blockquote, ul/ol, img, etc.)
1. Render entire article in a single page
1. Use CSS to create left/right tap zones for smooth scrolling
1. Store sanitized HTML in memory or cache, keyed by document ID

### HTML Output

Minimal markup with tap-zone navigation:

```
<html>
<head>
    <meta name="viewport" content="width=device-width">
    <style>
        body { font-family: serif; margin: 1em; line-height: 1.4; }
        img { max-width: 100%; }
        .tap-zone { position: fixed; top: 0; bottom: 0; width: 40%; cursor: pointer; }
        .tap-zone.left { left: 0; }
        .tap-zone.right { right: 0; }
        nav { margin-top: 1em; }
    </style>
</head>
<body>
    [content blocks]
    <div class="tap-zone left" onclick="scroll up"></div>
    <div class="tap-zone right" onclick="scroll down"></div>
    <nav>
        <a href="/archive/doc_id">Archive</a> | <a href="/">Back to list</a>
    </nav>
</body>
</html>
```

Keep CSS inline or in a single style block — avoid external stylesheets to reduce requests.

### Content Sanitization

Use something like `bleach` or `html-sanitizer` to strip the Readwise Reader HTML down to allowed tags: `p`, `h1`-`h6`, `blockquote`, `ul`, `ol`, `li`, `a`, `em`, `strong`, `img`, `br`. Remove all attributes except `href` on links and `src`/`alt` on images. This prevents layout-breaking CSS or weird markup from upstream.

### Caching

Two levels:

1. **Item list**: cache for a few minutes, refresh on explicit reload or after archiving
1. **Document content**: cache until archived or explicitly invalidated (content doesn't change)

In-memory dict is fine for personal use; you're not dealing with scale concerns.

### Configuration

```
READWISE_API_TOKEN=xxx
HOST=0.0.0.0
PORT=5000
CACHE_LIST_TTL=300
```

-----

That’s the skeleton. The Readwise Reader API calls and HTML sanitization are the fiddly bits; the rest is straightforward request handling.​​​​​​​​​​​​​​​​
