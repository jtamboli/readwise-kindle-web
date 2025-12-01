That simplifies things considerably. With a fixed target device, you can empirically determine your page budget once and hardcode it.

## Design Outline

### Server

Python with Flask or FastAPI. Single-user, no auth UI needed — just configure your Readwise Reader API token as an environment variable or config file.

### Data Flow

1. Server fetches items from Readwise Reader API on demand (with reasonable caching to avoid hammering the API)
1. For article content, server parses and sanitizes HTML, then paginates into chunks
1. Each page render updates reading progress via API call

### Routes

```
GET /
    List view of inbox items (title, source, maybe first line)
    Each item links to /read/<document_id>
    
GET /read/<document_id>
    Redirects to /read/<document_id>/1 (first page)
    
GET /read/<document_id>/<page_num>
    Renders one page of content
    Shows page N of M, prev/next links
    On load, PUTs reading progress to Readwise API (page_num / total_pages)
    
POST /archive/<document_id>
    Archives the item via API
    Redirects to / (or to next unread item, your preference)
```

### Pagination Logic

Preprocessor that takes sanitized HTML and splits into pages:

1. Parse HTML into block-level elements (p, h1-h6, blockquote, ul/ol, img, etc.)
1. Walk blocks, accumulating into current page
1. For text blocks: add to page if cumulative character count stays under budget; otherwise start new page
1. For images: close current page, put image on its own page (or image + following paragraph if you want)
1. Store paginated output in memory or cache, keyed by document ID

### HTML Output

Minimal markup. Something like:

```
<html>
<head>
    <meta name="viewport" content="width=device-width">
    <style>
        body { font-family: serif; margin: 1em; line-height: 1.4; }
        img { max-width: 100%; }
        nav { margin-top: 1em; }
    </style>
</head>
<body>
    [content blocks]
    <nav>
        <a href="prev">← Prev</a> | Page 3 of 12 | <a href="next">Next →</a>
        <br>
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
1. **Document content + pagination**: cache until archived or explicitly invalidated (content doesn’t change)

In-memory dict is fine for personal use; you’re not dealing with scale concerns.

### Configuration

```
READWISE_API_TOKEN=xxx
PAGE_CHAR_BUDGET=1800  # tune empirically
IMAGE_SEPARATE_PAGE=true
HOST=0.0.0.0
PORT=5000
```

### Determining Your Page Budget

Make a test route that renders Lorem Ipsum at various character counts (1000, 1500, 1800, 2000, 2500). Load each on your Kindle, note which fits comfortably without scrolling, use that as your budget. Do the same with a page containing one image to decide how to handle image pages.

-----

That’s the skeleton. The Readwise Reader API calls and HTML sanitization are the fiddly bits; the rest is straightforward request handling.​​​​​​​​​​​​​​​​
