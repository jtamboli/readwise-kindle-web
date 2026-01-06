// Package api provides the Readwise API client.
package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"time"

	"kindle-reader/internal/cache"
	"kindle-reader/internal/config"
)

// Client is the Readwise API client.
type Client struct {
	baseURL    string
	token      string
	httpClient *http.Client
	cache      *cache.Cache
	hiddenTag  string
	verbose    bool
}

// Document represents a Readwise document.
type Document = cache.Document

// ListItem represents an item in a list response.
type ListItem = cache.ListItem

// listResponse represents the API response for list endpoints.
type listResponse struct {
	Count          int        `json:"count"`
	NextPageCursor string     `json:"nextPageCursor"`
	Results        []ListItem `json:"results"`
}

// New creates a new Readwise API client.
func New(cfg *config.Config) *Client {
	return &Client{
		baseURL: cfg.ReadwiseAPIBase,
		token:   cfg.ReadwiseAPIToken,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		cache:     cache.New(cfg.CacheListTTL),
		hiddenTag: cfg.KindleHiddenTag,
		verbose:   cfg.Verbose,
	}
}

func (c *Client) log(format string, args ...interface{}) {
	if c.verbose {
		log.Printf(format, args...)
	}
}

// GetItemsByLocation fetches items from a specific location.
func (c *Client) GetItemsByLocation(location string, limit int) ([]ListItem, error) {
	if !config.ValidLocations[location] {
		return nil, fmt.Errorf("invalid location: %s", location)
	}

	// Check cache
	cacheKey := fmt.Sprintf("list_%s_%d", location, limit)
	if items, ok := c.cache.GetList(cacheKey); ok {
		c.log("Loading %s items from cache", location)
		return items, nil
	}

	c.log("Fetching %s items from Readwise API (max %d items)", location, limit)

	var allResults []ListItem
	var nextCursor string
	pageNum := 1

	for len(allResults) < limit {
		params := url.Values{}
		params.Set("location", location)
		if nextCursor != "" {
			params.Set("pageCursor", nextCursor)
		}

		c.log("  -> API request: GET /list/ (page %d, location=%s)", pageNum, location)

		reqURL := fmt.Sprintf("%s/list/?%s", c.baseURL, params.Encode())
		req, err := http.NewRequest("GET", reqURL, nil)
		if err != nil {
			return nil, err
		}
		req.Header.Set("Authorization", "Token "+c.token)
		req.Header.Set("Content-Type", "application/json")

		resp, err := c.httpClient.Do(req)
		if err != nil {
			return nil, err
		}

		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			return nil, err
		}

		if resp.StatusCode != http.StatusOK {
			return nil, fmt.Errorf("API error: %s", resp.Status)
		}

		var data listResponse
		if err := json.Unmarshal(body, &data); err != nil {
			return nil, err
		}

		allResults = append(allResults, data.Results...)
		c.log("  <- Received %d items (total: %d)", len(data.Results), len(allResults))

		nextCursor = data.NextPageCursor
		if nextCursor == "" {
			break
		}
		pageNum++
	}

	// Trim to limit if we fetched more
	if len(allResults) > limit {
		allResults = allResults[:limit]
	}

	// Cache the results
	c.cache.SetList(cacheKey, allResults)
	c.log("Cached %d %s items", len(allResults), location)

	return allResults, nil
}

// GetDocument fetches a single document with HTML content.
func (c *Client) GetDocument(docID string) (Document, error) {
	// Check cache
	if doc, ok := c.cache.GetDocument(docID); ok {
		c.log("Loading document %s from cache", docID)
		return doc, nil
	}

	c.log("Fetching document %s with HTML content from Readwise API", docID)

	params := url.Values{}
	params.Set("id", docID)
	params.Set("withHtmlContent", "true")

	c.log("  -> API request: GET /list/ (id=%s, withHtmlContent=true)", docID)

	reqURL := fmt.Sprintf("%s/list/?%s", c.baseURL, params.Encode())
	req, err := http.NewRequest("GET", reqURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Token "+c.token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API error: %s", resp.Status)
	}

	var data listResponse
	if err := json.Unmarshal(body, &data); err != nil {
		return nil, err
	}

	if len(data.Results) == 0 {
		c.log("  <- Document %s not found", docID)
		return nil, nil
	}

	document := Document(data.Results[0])
	title, _ := document["title"].(string)
	if title == "" {
		title = "Untitled"
	}
	htmlContent, _ := document["html_content"].(string)
	c.log("  <- Received document: '%s' (%d bytes HTML)", title, len(htmlContent))

	// Cache the document
	c.cache.SetDocument(docID, document)
	c.log("Cached document %s", docID)

	return document, nil
}

// UpdateReadingProgress updates reading progress for a document (fire-and-forget).
func (c *Client) UpdateReadingProgress(docID string, progress float64) {
	c.log("Updating reading progress for document %s to %.1f%%", docID, progress*100)

	go func() {
		c.log("  -> API request: PATCH /update/%s/ (reading_progress=%.2f)", docID, progress)

		body, _ := json.Marshal(map[string]interface{}{
			"reading_progress": progress,
		})

		req, err := http.NewRequest("PATCH", fmt.Sprintf("%s/update/%s/", c.baseURL, docID), bytes.NewReader(body))
		if err != nil {
			c.log("Error creating request: %v", err)
			return
		}
		req.Header.Set("Authorization", "Token "+c.token)
		req.Header.Set("Content-Type", "application/json")

		client := &http.Client{Timeout: 10 * time.Second}
		resp, err := client.Do(req)
		if err != nil {
			c.log("Error updating reading progress for %s: %v", docID, err)
			return
		}
		resp.Body.Close()

		if resp.StatusCode >= 400 {
			c.log("Error updating reading progress: %s", resp.Status)
			return
		}

		c.log("  <- Progress updated successfully")
	}()
}

// ArchiveDocument archives a document and invalidates caches.
func (c *Client) ArchiveDocument(docID string) error {
	c.log("Archiving document %s", docID)
	c.log("  -> API request: PATCH /update/%s/ (location=archive)", docID)

	body, _ := json.Marshal(map[string]interface{}{
		"location": "archive",
	})

	req, err := http.NewRequest("PATCH", fmt.Sprintf("%s/update/%s/", c.baseURL, docID), bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Token "+c.token)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("API error: %s", resp.Status)
	}

	c.log("  <- Document archived successfully")

	// Invalidate caches
	c.cache.InvalidateDocument(docID)
	c.cache.InvalidateLists()

	return nil
}

// GetLibraryArticles fetches articles from library locations (later and shortlist).
func (c *Client) GetLibraryArticles(limitPerLocation int) ([]ListItem, error) {
	// Check cache
	cacheKey := fmt.Sprintf("library_articles_%d", limitPerLocation)
	if items, ok := c.cache.GetList(cacheKey); ok {
		c.log("Loading library articles from cache")
		return items, nil
	}

	c.log("Fetching articles from library locations for tags (later, shortlist)")

	var allArticles []ListItem
	locations := []string{"later", "shortlist"}

	for _, location := range locations {
		items, err := c.GetItemsByLocation(location, limitPerLocation)
		if err != nil {
			c.log("Error fetching %s items: %v", location, err)
			continue
		}
		allArticles = append(allArticles, items...)
	}

	// Remove duplicates by ID
	seen := make(map[string]bool)
	var uniqueArticles []ListItem
	for _, article := range allArticles {
		id, ok := article["id"].(string)
		if !ok || id == "" {
			continue
		}
		if !seen[id] {
			seen[id] = true
			uniqueArticles = append(uniqueArticles, article)
		}
	}

	// Cache the results
	c.cache.SetList(cacheKey, uniqueArticles)
	c.log("Cached %d unique articles", len(uniqueArticles))

	return uniqueArticles, nil
}

// normalizeTags converts tags to a slice of strings.
func normalizeTags(tags interface{}) []string {
	switch t := tags.(type) {
	case map[string]interface{}:
		result := make([]string, 0, len(t))
		for k := range t {
			result = append(result, k)
		}
		return result
	case []interface{}:
		result := make([]string, 0, len(t))
		for _, v := range t {
			if s, ok := v.(string); ok {
				result = append(result, s)
			}
		}
		return result
	default:
		return nil
	}
}

// ToggleTag toggles a tag on an article (add if not present, remove if present).
// Returns true if tag was added, false if removed.
func (c *Client) ToggleTag(docID, tag string) (bool, error) {
	c.log("Toggling tag '%s' on document %s", tag, docID)

	// Fetch current article data to get tags
	article, err := c.GetDocument(docID)
	if err != nil {
		return false, err
	}
	if article == nil {
		return false, fmt.Errorf("document %s not found", docID)
	}

	currentTags := normalizeTags(article["tags"])

	// Check if tag exists
	hasTag := false
	for _, t := range currentTags {
		if t == tag {
			hasTag = true
			break
		}
	}

	var newTags []string
	var added bool

	if hasTag {
		// Remove the tag
		c.log("Removing tag '%s' from document %s", tag, docID)
		for _, t := range currentTags {
			if t != tag {
				newTags = append(newTags, t)
			}
		}
		added = false
	} else {
		// Add the tag
		c.log("Adding tag '%s' to document %s", tag, docID)
		newTags = append(currentTags, tag)
		added = true
	}

	// Update the article with new tags
	c.log("  -> API request: PATCH /update/%s/ (tags=%v)", docID, newTags)

	body, _ := json.Marshal(map[string]interface{}{
		"tags": newTags,
	})

	req, err := http.NewRequest("PATCH", fmt.Sprintf("%s/update/%s/", c.baseURL, docID), bytes.NewReader(body))
	if err != nil {
		return false, err
	}
	req.Header.Set("Authorization", "Token "+c.token)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return false, fmt.Errorf("API error: %s", resp.Status)
	}

	c.log("  <- Tags updated successfully")

	// Invalidate caches
	c.cache.InvalidateDocument(docID)
	c.cache.InvalidateLists()

	return added, nil
}

// InvalidateListCache clears the list cache.
func (c *Client) InvalidateListCache() {
	c.cache.InvalidateLists()
	c.log("Invalidated inbox list cache")
}

// IsArticleHidden checks if an article has the kindle-hidden tag.
func (c *Client) IsArticleHidden(article ListItem) bool {
	tags := normalizeTags(article["tags"])
	for _, t := range tags {
		if t == c.hiddenTag {
			return true
		}
	}
	return false
}

// HiddenTag returns the hidden tag name.
func (c *Client) HiddenTag() string {
	return c.hiddenTag
}
