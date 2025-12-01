"""HTML pagination engine for Kindle display."""
from typing import List, Tuple
from bs4 import BeautifulSoup, Tag
from app.config import Config


# Block-level elements to paginate
BLOCK_ELEMENTS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "ul", "ol", "img"]

# Cache for paginated documents
pagination_cache: dict[str, Tuple[List[str], int]] = {}


def get_text_length(element: Tag) -> int:
    """
    Get the text length of an element.

    Args:
        element: BeautifulSoup Tag

    Returns:
        Character count of the element's text content
    """
    return len(element.get_text(strip=True))


def paginate_html(html: str, doc_id: str) -> Tuple[List[str], int]:
    """
    Paginate HTML content into Kindle-sized pages.

    Preserves block integrity - entire block-level elements are kept together
    even if they exceed the character budget.

    Args:
        html: Sanitized HTML content
        doc_id: Document ID (for caching)

    Returns:
        Tuple of (list of page HTML strings, total page count)
    """
    # Check cache
    if doc_id in pagination_cache:
        return pagination_cache[doc_id]

    if not html:
        empty_result = (["<p>No content available.</p>"], 1)
        pagination_cache[doc_id] = empty_result
        return empty_result

    # Parse HTML
    soup = BeautifulSoup(html, "html.parser")

    # Extract block-level elements
    blocks = []
    for element in soup.find_all(BLOCK_ELEMENTS):
        # Skip nested elements (e.g., li inside ul)
        if element.parent.name in BLOCK_ELEMENTS and element.name != element.parent.name:
            continue
        blocks.append(element)

    if not blocks:
        # No block elements found, wrap everything in a paragraph
        content = soup.get_text(strip=True)
        if not content:
            empty_result = (["<p>No content available.</p>"], 1)
            pagination_cache[doc_id] = empty_result
            return empty_result
        blocks = [BeautifulSoup(f"<p>{content}</p>", "html.parser").p]

    # Paginate blocks
    pages: List[List[Tag]] = []
    current_page: List[Tag] = []
    current_char_count = 0

    for block in blocks:
        block_length = get_text_length(block)

        # Handle images
        if block.name == "img":
            if Config.IMAGE_SEPARATE_PAGE:
                # Close current page if it has content
                if current_page:
                    pages.append(current_page)
                    current_page = []
                    current_char_count = 0

                # Image on its own page
                pages.append([block])
                continue
            else:
                # Treat image like a block
                pass

        # Check if adding this block would exceed budget
        if current_char_count > 0 and current_char_count + block_length > Config.KINDLE_PAGE_CHAR_BUDGET:
            # Start new page
            pages.append(current_page)
            current_page = [block]
            current_char_count = block_length
        else:
            # Add to current page
            current_page.append(block)
            current_char_count += block_length

    # Add final page
    if current_page:
        pages.append(current_page)

    # Convert pages to HTML strings
    page_htmls = []
    for page_blocks in pages:
        page_html = "\n".join(str(block) for block in page_blocks)
        page_htmls.append(page_html)

    total_pages = len(page_htmls)
    result = (page_htmls, total_pages)

    # Cache the result
    pagination_cache[doc_id] = result

    return result


def invalidate_pagination_cache(doc_id: str):
    """Invalidate cached pagination for a document."""
    if doc_id in pagination_cache:
        del pagination_cache[doc_id]
