// Package cache provides caching for API responses.
package cache

import (
	"sync"
	"time"
)

// Document represents a cached document.
type Document map[string]interface{}

// ListItem represents an item in a cached list.
type ListItem map[string]interface{}

// cacheEntry holds a cached value with its expiration time.
type cacheEntry struct {
	value     []ListItem
	expiresAt time.Time
}

// Cache provides two-tier caching for list and document data.
type Cache struct {
	listCache     map[string]cacheEntry
	documentCache map[string]Document
	listMu        sync.RWMutex
	docMu         sync.RWMutex
	ttl           time.Duration
}

// New creates a new cache with the specified TTL in seconds.
func New(ttlSeconds int) *Cache {
	return &Cache{
		listCache:     make(map[string]cacheEntry),
		documentCache: make(map[string]Document),
		ttl:           time.Duration(ttlSeconds) * time.Second,
	}
}

// GetList retrieves a list from cache if it exists and hasn't expired.
func (c *Cache) GetList(key string) ([]ListItem, bool) {
	c.listMu.RLock()
	defer c.listMu.RUnlock()

	entry, ok := c.listCache[key]
	if !ok {
		return nil, false
	}

	if time.Now().After(entry.expiresAt) {
		return nil, false
	}

	return entry.value, true
}

// SetList stores a list in cache with TTL.
func (c *Cache) SetList(key string, items []ListItem) {
	c.listMu.Lock()
	defer c.listMu.Unlock()

	c.listCache[key] = cacheEntry{
		value:     items,
		expiresAt: time.Now().Add(c.ttl),
	}
}

// GetDocument retrieves a document from cache.
func (c *Cache) GetDocument(docID string) (Document, bool) {
	c.docMu.RLock()
	defer c.docMu.RUnlock()

	doc, ok := c.documentCache[docID]
	return doc, ok
}

// SetDocument stores a document in cache (no TTL, invalidated manually).
func (c *Cache) SetDocument(docID string, doc Document) {
	c.docMu.Lock()
	defer c.docMu.Unlock()

	c.documentCache[docID] = doc
}

// InvalidateDocument removes a document from cache.
func (c *Cache) InvalidateDocument(docID string) {
	c.docMu.Lock()
	defer c.docMu.Unlock()

	delete(c.documentCache, docID)
}

// InvalidateLists clears all list caches.
func (c *Cache) InvalidateLists() {
	c.listMu.Lock()
	defer c.listMu.Unlock()

	c.listCache = make(map[string]cacheEntry)
}

// InvalidateAll clears both list and document caches.
func (c *Cache) InvalidateAll() {
	c.InvalidateLists()

	c.docMu.Lock()
	defer c.docMu.Unlock()
	c.documentCache = make(map[string]Document)
}
