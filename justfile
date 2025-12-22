# Readwise Kindle Web Reader - Development Commands

# Serve test pages on local network (accessible from Kindle)
serve-tests:
    #!/usr/bin/env bash
    PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()")
    IP=$(ipconfig getifaddr en0)
    echo "Serving test pages at http://${IP}:${PORT}/"
    echo "Open this URL on your Kindle to test"
    python3 -m http.server "$PORT" --bind 0.0.0.0 --directory test-pages
