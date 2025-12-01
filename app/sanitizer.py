"""HTML sanitization for Kindle browser."""
import bleach

# Allowed HTML tags for Kindle compatibility
ALLOWED_TAGS = [
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "ul",
    "ol",
    "li",
    "a",
    "em",
    "strong",
    "img",
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
