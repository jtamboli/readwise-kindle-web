# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /build

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -o kindle-reader ./cmd/server/

# Runtime stage
FROM alpine:3.19

WORKDIR /app

# Copy binary and templates
COPY --from=builder /build/kindle-reader .
COPY --from=builder /build/templates ./templates

# Set environment variables
ENV PORT=8000
ENV HOST=0.0.0.0
ENV TEMPLATES_DIR=/app/templates

EXPOSE 8000

CMD ["./kindle-reader"]
