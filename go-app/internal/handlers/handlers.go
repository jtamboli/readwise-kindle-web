// Package handlers provides HTTP handlers for the web application.
package handlers

import (
	"fmt"
	"html/template"
	"math/rand"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"

	"kindle-reader/internal/api"
	"kindle-reader/internal/config"
	"kindle-reader/internal/sanitizer"
	"kindle-reader/internal/suntimes"
)

// 1x1 transparent GIF for progress tracking beacon
var transparentGIF = []byte{
	0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 0x01, 0x00, 0x01, 0x00, 0x80, 0x00,
	0x00, 0xff, 0xff, 0xff, 0x00, 0x00, 0x00, 0x21, 0xf9, 0x04, 0x01, 0x00,
	0x00, 0x00, 0x00, 0x2c, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00,
	0x00, 0x02, 0x02, 0x44, 0x01, 0x00, 0x3b,
}

// Handler holds the dependencies for HTTP handlers.
type Handler struct {
	client    *api.Client
	templates *template.Template
}

// New creates a new Handler.
func New(client *api.Client, templatesDir string) (*Handler, error) {
	// Define template functions
	funcMap := template.FuncMap{
		"extractDomain":  extractDomain,
		"wordsToMinutes": wordsToMinutes,
		"truncate":       truncate,
		"safeHTML":       safeHTML,
	}

	// Parse all templates
	tmpl, err := template.New("").Funcs(funcMap).ParseGlob(templatesDir + "/*.html")
	if err != nil {
		return nil, fmt.Errorf("error parsing templates: %w", err)
	}

	return &Handler{
		client:    client,
		templates: tmpl,
	}, nil
}

// extractDomain extracts the domain from a URL, removing 'www.' prefix.
func extractDomain(urlStr string) string {
	if urlStr == "" {
		return ""
	}
	parsed, err := url.Parse(urlStr)
	if err != nil {
		return ""
	}
	domain := parsed.Host
	if domain == "" {
		domain = parsed.Path
	}
	domain = strings.TrimPrefix(domain, "www.")
	return domain
}

// wordsToMinutes converts word count to estimated reading time in minutes.
func wordsToMinutes(wordCount interface{}) int {
	var count int
	switch v := wordCount.(type) {
	case int:
		count = v
	case float64:
		count = int(v)
	case nil:
		return 0
	default:
		return 0
	}
	if count <= 0 {
		return 0
	}
	// Average reading speed: 238 words per minute
	minutes := (count + 237) / 238
	if minutes < 1 {
		minutes = 1
	}
	return minutes
}

// truncate truncates a string to the specified length.
func truncate(s string, length int) string {
	if len(s) <= length {
		return s
	}
	return s[:length] + "..."
}

// safeHTML marks a string as safe HTML.
func safeHTML(s string) template.HTML {
	return template.HTML(s)
}

// filterHiddenArticles removes articles with the kindle-hidden tag.
func (h *Handler) filterHiddenArticles(items []api.ListItem) []api.ListItem {
	result := make([]api.ListItem, 0, len(items))
	for _, item := range items {
		if !h.client.IsArticleHidden(item) {
			result = append(result, item)
		}
	}
	return result
}

// filterSeenArticles removes articles that have been seen.
func filterSeenArticles(items []api.ListItem) []api.ListItem {
	result := make([]api.ListItem, 0, len(items))
	for _, item := range items {
		seen, _ := item["seen"].(bool)
		if !seen {
			result = append(result, item)
		}
	}
	return result
}

// sortByRecentActivity sorts items by last_opened_at, falling back to last_moved_at.
func sortByRecentActivity(items []api.ListItem) []api.ListItem {
	sort.Slice(items, func(i, j int) bool {
		getKey := func(item api.ListItem) string {
			if opened, ok := item["last_opened_at"].(string); ok && opened != "" {
				return opened
			}
			if moved, ok := item["last_moved_at"].(string); ok {
				return moved
			}
			return ""
		}
		return getKey(items[i]) > getKey(items[j])
	})
	return items
}

// ListHome handles the home page.
func (h *Handler) ListHome(w http.ResponseWriter, r *http.Request) {
	isDark := suntimes.IsDarkMode()

	shortlistItems, err := h.client.GetItemsByLocation("shortlist", 5)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error fetching items: %v", err), http.StatusInternalServerError)
		return
	}

	laterItems, err := h.client.GetItemsByLocation("later", 20)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error fetching items: %v", err), http.StatusInternalServerError)
		return
	}

	// Filter and sort
	shortlistItems = h.filterHiddenArticles(shortlistItems)
	laterItems = h.filterHiddenArticles(laterItems)
	shortlistItems = sortByRecentActivity(shortlistItems)
	laterItems = sortByRecentActivity(laterItems)

	data := map[string]interface{}{
		"ShortlistItems": shortlistItems,
		"LaterItems":     laterItems,
		"IsDark":         isDark,
	}

	if err := h.templates.ExecuteTemplate(w, "list.html", data); err != nil {
		http.Error(w, fmt.Sprintf("Error rendering template: %v", err), http.StatusInternalServerError)
	}
}

// ReadArticle handles displaying a full article.
func (h *Handler) ReadArticle(w http.ResponseWriter, r *http.Request) {
	// Extract doc_id from path: /read/{doc_id}
	docID := strings.TrimPrefix(r.URL.Path, "/read/")
	docID = strings.TrimPrefix(docID, "/kindle/read/")
	if docID == "" {
		http.Error(w, "Document ID required", http.StatusBadRequest)
		return
	}

	document, err := h.client.GetDocument(docID)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error fetching document: %v", err), http.StatusInternalServerError)
		return
	}
	if document == nil {
		http.Error(w, "Document not found", http.StatusNotFound)
		return
	}

	htmlContent, _ := document["html_content"].(string)
	if htmlContent == "" {
		http.Error(w, "Document has no content", http.StatusNotFound)
		return
	}

	// Sanitize HTML
	cleanHTML := sanitizer.Sanitize(htmlContent)

	isDark := suntimes.IsDarkMode()
	readingProgress := 0.0
	if p, ok := document["reading_progress"].(float64); ok {
		readingProgress = p
	}

	title, _ := document["title"].(string)
	if title == "" {
		title = "Untitled"
	}

	data := map[string]interface{}{
		"DocID":           docID,
		"Title":           title,
		"Author":          document["author"],
		"Source":          document["source"],
		"Content":         cleanHTML,
		"IsDark":          isDark,
		"ReadingProgress": readingProgress,
	}

	if err := h.templates.ExecuteTemplate(w, "page.html", data); err != nil {
		http.Error(w, fmt.Sprintf("Error rendering template: %v", err), http.StatusInternalServerError)
	}
}

// UpdateProgress handles reading progress updates via beacon.
func (h *Handler) UpdateProgress(w http.ResponseWriter, r *http.Request) {
	// Extract doc_id from path: /progress/{doc_id}
	docID := strings.TrimPrefix(r.URL.Path, "/progress/")
	docID = strings.TrimPrefix(docID, "/kindle/progress/")
	if docID == "" {
		http.Error(w, "Document ID required", http.StatusBadRequest)
		return
	}

	// Get progress from query param
	progress := 0.0
	if pStr := r.URL.Query().Get("p"); pStr != "" {
		if p, err := strconv.ParseFloat(pStr, 64); err == nil {
			progress = p
		}
	}

	// Clamp progress
	if progress < 0 {
		progress = 0
	}
	if progress > 1 {
		progress = 1
	}

	// Fire-and-forget update
	h.client.UpdateReadingProgress(docID, progress)

	// Return transparent GIF
	w.Header().Set("Content-Type", "image/gif")
	w.Write(transparentGIF)
}

// Archive handles archiving a document.
func (h *Handler) Archive(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Extract doc_id from path: /archive/{doc_id}
	docID := strings.TrimPrefix(r.URL.Path, "/archive/")
	docID = strings.TrimPrefix(docID, "/kindle/archive/")
	if docID == "" {
		http.Error(w, "Document ID required", http.StatusBadRequest)
		return
	}

	if err := h.client.ArchiveDocument(docID); err != nil {
		http.Error(w, fmt.Sprintf("Error archiving document: %v", err), http.StatusInternalServerError)
		return
	}

	http.Redirect(w, r, "/kindle/", http.StatusSeeOther)
}

// ListByLocation handles displaying items from a specific location.
func (h *Handler) ListByLocation(w http.ResponseWriter, r *http.Request) {
	// Extract location from path: /list/{location}
	location := strings.TrimPrefix(r.URL.Path, "/list/")
	location = strings.TrimPrefix(location, "/kindle/list/")
	if location == "" {
		http.Error(w, "Location required", http.StatusBadRequest)
		return
	}

	if !config.ValidLocations[location] {
		http.Error(w, fmt.Sprintf("Invalid location: %s", location), http.StatusBadRequest)
		return
	}

	isDark := suntimes.IsDarkMode()

	items, err := h.client.GetItemsByLocation(location, 100)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error fetching items: %v", err), http.StatusInternalServerError)
		return
	}

	// Filter and sort
	items = h.filterHiddenArticles(items)
	items = sortByRecentActivity(items)

	// Capitalize location for display
	displayName := strings.Title(location)

	data := map[string]interface{}{
		"Items":    items,
		"ListName": displayName,
		"IsDark":   isDark,
	}

	if err := h.templates.ExecuteTemplate(w, "list_single.html", data); err != nil {
		http.Error(w, fmt.Sprintf("Error rendering template: %v", err), http.StatusInternalServerError)
	}
}

// ListFeed handles displaying feed items.
func (h *Handler) ListFeed(w http.ResponseWriter, r *http.Request) {
	isDark := suntimes.IsDarkMode()

	items, err := h.client.GetItemsByLocation("feed", 100)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error fetching items: %v", err), http.StatusInternalServerError)
		return
	}

	// Filter hidden and seen articles
	items = h.filterHiddenArticles(items)
	items = filterSeenArticles(items)
	items = sortByRecentActivity(items)

	data := map[string]interface{}{
		"Items":    items,
		"ListName": "Feed",
		"IsDark":   isDark,
	}

	if err := h.templates.ExecuteTemplate(w, "list_single.html", data); err != nil {
		http.Error(w, fmt.Sprintf("Error rendering template: %v", err), http.StatusInternalServerError)
	}
}

// ListRandom handles displaying random articles.
func (h *Handler) ListRandom(w http.ResponseWriter, r *http.Request) {
	isDark := suntimes.IsDarkMode()

	laterItems, err := h.client.GetItemsByLocation("later", 100)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error fetching items: %v", err), http.StatusInternalServerError)
		return
	}

	shortlistItems, err := h.client.GetItemsByLocation("shortlist", 100)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error fetching items: %v", err), http.StatusInternalServerError)
		return
	}

	// Combine all articles
	allItems := append(laterItems, shortlistItems...)

	// Filter hidden articles
	allItems = h.filterHiddenArticles(allItems)

	// Remove duplicates by ID
	seen := make(map[string]bool)
	var uniqueItems []api.ListItem
	for _, item := range allItems {
		id, ok := item["id"].(string)
		if !ok || id == "" {
			continue
		}
		if !seen[id] {
			seen[id] = true
			uniqueItems = append(uniqueItems, item)
		}
	}

	// Shuffle
	rand.Shuffle(len(uniqueItems), func(i, j int) {
		uniqueItems[i], uniqueItems[j] = uniqueItems[j], uniqueItems[i]
	})

	// Take first 10
	if len(uniqueItems) > 10 {
		uniqueItems = uniqueItems[:10]
	}

	data := map[string]interface{}{
		"Items":    uniqueItems,
		"ListName": "Random",
		"IsDark":   isDark,
	}

	if err := h.templates.ExecuteTemplate(w, "list_single.html", data); err != nil {
		http.Error(w, fmt.Sprintf("Error rendering template: %v", err), http.StatusInternalServerError)
	}
}

// ListTags handles displaying all tags.
func (h *Handler) ListTags(w http.ResponseWriter, r *http.Request) {
	isDark := suntimes.IsDarkMode()

	articles, err := h.client.GetLibraryArticles(100)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error fetching articles: %v", err), http.StatusInternalServerError)
		return
	}

	// Count tags
	tagCounts := make(map[string]int)
	for _, article := range articles {
		tags := article["tags"]
		var tagNames []string

		switch t := tags.(type) {
		case map[string]interface{}:
			for k := range t {
				tagNames = append(tagNames, k)
			}
		case []interface{}:
			for _, v := range t {
				if s, ok := v.(string); ok {
					tagNames = append(tagNames, s)
				}
			}
		}

		for _, tagName := range tagNames {
			if tagName != "" {
				tagCounts[tagName]++
			}
		}
	}

	// Convert to list and sort by count
	type tagItem struct {
		Name  string
		Count int
	}
	var tags []tagItem
	for name, count := range tagCounts {
		tags = append(tags, tagItem{Name: name, Count: count})
	}
	sort.Slice(tags, func(i, j int) bool {
		return tags[i].Count > tags[j].Count
	})

	data := map[string]interface{}{
		"Tags":   tags,
		"IsDark": isDark,
	}

	if err := h.templates.ExecuteTemplate(w, "tags.html", data); err != nil {
		http.Error(w, fmt.Sprintf("Error rendering template: %v", err), http.StatusInternalServerError)
	}
}

// ListArticlesByTag handles displaying articles with a specific tag.
func (h *Handler) ListArticlesByTag(w http.ResponseWriter, r *http.Request) {
	// Extract tag_name from path: /tags/{tag_name}
	tagName := strings.TrimPrefix(r.URL.Path, "/tags/")
	tagName = strings.TrimPrefix(tagName, "/kindle/tags/")
	if tagName == "" {
		// If no tag specified, show tag list
		h.ListTags(w, r)
		return
	}

	isDark := suntimes.IsDarkMode()

	articles, err := h.client.GetLibraryArticles(100)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error fetching articles: %v", err), http.StatusInternalServerError)
		return
	}

	// Filter articles by tag
	var filteredItems []api.ListItem
	for _, article := range articles {
		tags := article["tags"]
		var tagNames []string

		switch t := tags.(type) {
		case map[string]interface{}:
			for k := range t {
				tagNames = append(tagNames, k)
			}
		case []interface{}:
			for _, v := range t {
				if s, ok := v.(string); ok {
					tagNames = append(tagNames, s)
				}
			}
		}

		for _, t := range tagNames {
			if t == tagName {
				filteredItems = append(filteredItems, article)
				break
			}
		}
	}

	// Filter and sort
	filteredItems = h.filterHiddenArticles(filteredItems)
	filteredItems = sortByRecentActivity(filteredItems)

	data := map[string]interface{}{
		"Items":    filteredItems,
		"ListName": fmt.Sprintf("Tag: %s", tagName),
		"IsDark":   isDark,
	}

	if err := h.templates.ExecuteTemplate(w, "list_single.html", data); err != nil {
		http.Error(w, fmt.Sprintf("Error rendering template: %v", err), http.StatusInternalServerError)
	}
}

// ToggleHidden handles toggling the hidden status of an article.
func (h *Handler) ToggleHidden(w http.ResponseWriter, r *http.Request) {
	// Extract doc_id from path: /hide/{doc_id}
	docID := strings.TrimPrefix(r.URL.Path, "/hide/")
	docID = strings.TrimPrefix(docID, "/kindle/hide/")
	if docID == "" {
		http.Error(w, "Document ID required", http.StatusBadRequest)
		return
	}

	_, err := h.client.ToggleTag(docID, h.client.HiddenTag())
	if err != nil {
		http.Error(w, fmt.Sprintf("Error toggling hidden status: %v", err), http.StatusInternalServerError)
		return
	}

	// Redirect back to referer or home
	referer := r.Header.Get("Referer")
	if referer != "" && strings.Contains(referer, "/kindle/") {
		http.Redirect(w, r, referer, http.StatusSeeOther)
	} else {
		http.Redirect(w, r, "/kindle/", http.StatusSeeOther)
	}
}

// RefreshCache handles clearing all caches.
func (h *Handler) RefreshCache(w http.ResponseWriter, r *http.Request) {
	h.client.InvalidateListCache()
	http.Redirect(w, r, "/kindle/", http.StatusSeeOther)
}

// Health handles health check.
func (h *Handler) Health(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"status":"ok"}`))
}
