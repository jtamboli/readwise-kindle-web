// Package sanitizer provides HTML sanitization for Kindle browser compatibility.
package sanitizer

import (
	"github.com/microcosm-cc/bluemonday"
)

var policy *bluemonday.Policy

func init() {
	policy = bluemonday.NewPolicy()

	// Headings
	policy.AllowElements("h1", "h2", "h3", "h4", "h5", "h6")

	// Block elements
	policy.AllowElements("p", "blockquote", "pre", "hr")

	// Lists
	policy.AllowElements("ul", "ol", "li")

	// Tables
	policy.AllowElements("table", "thead", "tbody", "tr", "th", "td")

	// Inline formatting
	policy.AllowElements("em", "i", "strong", "b", "code", "sup", "sub")

	// Links with href attribute
	policy.AllowAttrs("href").OnElements("a")
	policy.AllowElements("a")

	// Media - images with src and alt attributes
	policy.AllowAttrs("src", "alt").OnElements("img")
	policy.AllowElements("img", "figure", "figcaption")

	// Misc
	policy.AllowElements("br")
}

// Sanitize cleans HTML content for safe Kindle rendering.
func Sanitize(html string) string {
	if html == "" {
		return ""
	}
	return policy.Sanitize(html)
}
