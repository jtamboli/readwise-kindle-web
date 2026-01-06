// Package config provides configuration management for the Kindle reader application.
package config

import (
	"fmt"
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

// Config holds the application configuration.
type Config struct {
	ReadwiseAPIToken   string
	ReadwiseAPIBase    string
	CacheListTTL       int
	KindleHiddenTag    string
	Verbose            bool
}

// ValidLocations is the set of valid location values for the API.
var ValidLocations = map[string]bool{
	"new":       true,
	"later":     true,
	"shortlist": true,
	"archive":   true,
	"feed":      true,
}

// Load loads configuration from environment variables.
func Load() (*Config, error) {
	// Load .env file if it exists
	_ = godotenv.Load()

	token := os.Getenv("READWISE_API_TOKEN")
	if token == "" {
		return nil, fmt.Errorf("READWISE_API_TOKEN environment variable is required")
	}

	cacheTTL := 300 // 5 minutes default
	if ttlStr := os.Getenv("CACHE_LIST_TTL"); ttlStr != "" {
		if parsed, err := strconv.Atoi(ttlStr); err == nil {
			cacheTTL = parsed
		}
	}

	verbose := false
	if v := os.Getenv("KINDLE_READWISE_VERBOSE"); v == "true" {
		verbose = true
	}

	return &Config{
		ReadwiseAPIToken:   token,
		ReadwiseAPIBase:    "https://readwise.io/api/v3",
		CacheListTTL:       cacheTTL,
		KindleHiddenTag:    "kindle-hidden",
		Verbose:            verbose,
	}, nil
}
