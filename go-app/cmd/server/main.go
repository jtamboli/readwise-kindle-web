// Package main is the entry point for the Kindle reader web application.
package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

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
		port = "9002"
	}

	// Get host from environment or default (localhost only for container setup)
	host := os.Getenv("HOST")
	if host == "" {
		host = "127.0.0.1"
	}

	addr := host + ":" + port

	// Create server with timeouts
	server := &http.Server{
		Addr:         addr,
		Handler:      mux,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 60 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// Graceful shutdown on SIGTERM/SIGINT
	done := make(chan bool, 1)
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-quit
		log.Println("Shutting down server...")

		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		if err := server.Shutdown(ctx); err != nil {
			log.Fatalf("Server forced to shutdown: %v", err)
		}

		close(done)
	}()

	log.Printf("Starting Readwise Kindle Web Reader on %s", addr)
	log.Printf("Templates directory: %s", templatesDir)

	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}

	<-done
	log.Println("Server stopped")
}
