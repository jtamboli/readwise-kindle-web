"""HTML sanitization for Kindle browser."""
import bleach

# Allowed HTML tags for Kindle compatibility
ALLOWED_TAGS = [
    # Headings
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    # Block elements
    "p",
    "blockquote",
    "pre",
    "hr",
    # Lists
    "ul",
    "ol",
    "li",
    # Tables
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    # Inline formatting
    "a",
    "em",
    "i",
    "strong",
    "b",
    "code",
    "sup",
    "sub",
    # Media
    "img",
    "figure",
    "figcaption",
    # Misc
    "br",
]

# Allowed attributes per tag
ALLOWED_ATTRS = {
    "a": ["href"],
    "img": ["src", "alt"],
}


def sanitize_html(html: str) -> str:
    """
    Sanitize HTML content for safe Kindle rendering.

    Args:
        html: Raw HTML content

    Returns:
        Sanitized HTML with only allowed tags and attributes
    """
    if not html:
        return ""

    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True,  # Strip disallowed tags instead of escaping
    )
