// Package main is the entry point for the Kindle reader web application.
package main

import (
	"log"
	"net/http"
	"os"
	"strings"

	"kindle-reader/internal/api"
	"kindle-reader/internal/config"
	"kindle-reader/internal/handlers"
)

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// Create API client
	client := api.New(cfg)

	// Determine templates directory
	templatesDir := "templates"
	if dir := os.Getenv("TEMPLATES_DIR"); dir != "" {
		templatesDir = dir
	}

	// Create handlers
	h, err := handlers.New(client, templatesDir)
	if err != nil {
		log.Fatalf("Failed to initialize handlers: %v", err)
	}

	// Create router
	mux := http.NewServeMux()

	// Wrapper to strip /kindle prefix
	stripPrefix := func(next http.HandlerFunc) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			r.URL.Path = strings.TrimPrefix(r.URL.Path, "/kindle")
			if r.URL.Path == "" {
				r.URL.Path = "/"
			}
			next(w, r)
		}
	}

	// Register routes with /kindle prefix support
	registerRoute := func(pattern string, handler http.HandlerFunc) {
		mux.HandleFunc(pattern, handler)
		mux.HandleFunc("/kindle"+pattern, stripPrefix(handler))
	}

	// Routes
	registerRoute("/", h.ListHome)
	registerRoute("/health", h.Health)
	registerRoute("/refresh", h.RefreshCache)
	registerRoute("/feed", h.ListFeed)
	registerRoute("/random", h.ListRandom)

	// Routes with path parameters need special handling
	mux.HandleFunc("/read/", h.ReadArticle)
	mux.HandleFunc("/kindle/read/", h.ReadArticle)

	mux.HandleFunc("/progress/", h.UpdateProgress)
	mux.HandleFunc("/kindle/progress/", h.UpdateProgress)

	mux.HandleFunc("/archive/", h.Archive)
	mux.HandleFunc("/kindle/archive/", h.Archive)

	mux.HandleFunc("/list/", h.ListByLocation)
	mux.HandleFunc("/kindle/list/", h.ListByLocation)

	mux.HandleFunc("/tags/", h.ListArticlesByTag)
	mux.HandleFunc("/kindle/tags/", h.ListArticlesByTag)

	mux.HandleFunc("/tags", h.ListTags)
	mux.HandleFunc("/kindle/tags", h.ListTags)

	mux.HandleFunc("/hide/", h.ToggleHidden)
	mux.HandleFunc("/kindle/hide/", h.ToggleHidden)

	// Get port from environment or default
	port := os.Getenv("PORT")
	if port == "" {
		port = "8000"
	}

	// Get host from environment or default
	host := os.Getenv("HOST")
	if host == "" {
		host = "0.0.0.0"
	}

	addr := host + ":" + port

	log.Printf("Starting Readwise Kindle Web Reader on %s", addr)
	log.Printf("Templates directory: %s", templatesDir)

	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
