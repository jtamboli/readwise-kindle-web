# Container Integration Guide

This guide explains how to integrate the Go Kindle Reader into an existing Docker container with supervisord and nginx.

## Service Specifications

| Item | Value |
|------|-------|
| **Port** | `9002` |
| **Host** | `127.0.0.1` (localhost only) |
| **URL paths** | `/kindle/*` |
| **HTTP methods** | GET, POST |
| **Health endpoint** | `/kindle/health` → `{"status":"ok"}` |
| **Startup time** | <1 second |
| **Binary size** | ~8.5MB (static, no CGO) |

## Build

Build a static binary for Linux:

```bash
cd go-app
CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o kindle-reader ./cmd/server/
```

## Files to Copy into Container

```
/app/bin/kindle-reader              # Binary (from build step)
/app/kindle-reader/templates/       # Template directory
  ├── list.html
  ├── list_single.html
  ├── page.html
  └── tags.html
```

## Environment Variables

Add to your container's `.env` file:

```bash
# Required
READWISE_API_TOKEN=<your_token>

# Required - path to templates
TEMPLATES_DIR=/app/kindle-reader/templates

# Optional (these are the defaults)
# PORT=9002
# HOST=127.0.0.1
# CACHE_LIST_TTL=300
# KINDLE_READWISE_VERBOSE=false
```

## Supervisord Configuration

Add to your supervisord config:

```ini
[program:kindle-reader]
command=/app/bin/kindle-reader
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
stopsignal=TERM
stopwaitsecs=15
```

The service handles SIGTERM gracefully with a 10-second timeout for in-flight requests.

## Nginx Configuration

Add to your nginx config:

```nginx
location /kindle/ {
    proxy_pass http://127.0.0.1:9002;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Dockerfile Integration

If building as part of a multi-stage Docker build:

```dockerfile
# Build stage for Go binary
FROM golang:1.21-alpine AS kindle-builder
WORKDIR /build
COPY go-app/go.mod go-app/go.sum ./
RUN go mod download
COPY go-app/ .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o kindle-reader ./cmd/server/

# In your main container stage
FROM node:20-alpine
# ... your existing setup ...

# Copy Kindle Reader binary and templates
COPY --from=kindle-builder /build/kindle-reader /app/bin/kindle-reader
COPY go-app/templates /app/kindle-reader/templates

# ... rest of your Dockerfile ...
```

## Health Check

The service exposes a health endpoint:

```bash
curl http://127.0.0.1:9002/kindle/health
# Response: {"status":"ok"}
```

## Security Notes

- Service listens on localhost only (127.0.0.1)
- No authentication built-in (relies on nginx/infrastructure)
- No persistent data storage required
- No CORS headers (server-rendered HTML pages)

## Troubleshooting

**Service won't start:**
- Check `READWISE_API_TOKEN` is set
- Check `TEMPLATES_DIR` points to valid template files
- Check port 9002 is not in use

**Templates not found:**
- Verify `TEMPLATES_DIR` environment variable
- Ensure all 4 template files exist in the directory

**API errors:**
- Verify Readwise API token is valid
- Check network connectivity to `readwise.io`
