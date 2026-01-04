# Readwise Kindle Web Reader - Development Commands

# Serve test pages on local network (accessible from Kindle)
serve-tests:
    #!/usr/bin/env bash
    PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()")
    IP=$(ipconfig getifaddr en0)
    echo "Serving test pages at http://${IP}:${PORT}/"
    echo "Open this URL on your Kindle to test"
    python3 -m http.server "$PORT" --bind 0.0.0.0 --directory test-pages

# Fetch document list from Readwise API and print as JSON
get-documents location="later":
    #!/usr/bin/env bash
    if [ -z "$READER_API_KEY" ]; then
        echo "Error: READER_API_KEY environment variable not set" >&2
        exit 1
    fi
    curl -s "https://readwise.io/api/v3/list/?location={{location}}" \
        -H "Authorization: Token $READER_API_KEY" \
        -H "Content-Type: application/json"

# Fetch a specific document by ID with HTML content
get-document doc_id="01kchnw4xx55e1n8twekqybjhm":
    #!/usr/bin/env bash
    if [ -z "$READER_API_KEY" ]; then
        echo "Error: READER_API_KEY environment variable not set" >&2
        exit 1
    fi
    curl -s "https://readwise.io/api/v3/list/?id={{doc_id}}&withHtmlContent=true" \
        -H "Authorization: Token $READER_API_KEY" \
        -H "Content-Type: application/json"
