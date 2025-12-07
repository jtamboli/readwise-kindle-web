"""HTML pagination engine for Kindle display."""
from typing import List, Tuple
from bs4 import BeautifulSoup, Tag
from kindle_reader.config import Config


# Block-level elements to paginate
BLOCK_ELEMENTS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "ul", "ol", "img"]


def calculate_effective_size(html_block: str) -> int:
    """
    Calculate effective size of an HTML block using compound cost model.

    This uses the empirically-calibrated cost formula that accounts for
    the vertical space taken by different HTML elements on Kindle.

    Args:
        html_block: String of HTML content

    Returns:
        Effective size (integer) representing vertical space consumption
    """
    soup = BeautifulSoup(html_block, "html.parser")

    # Count raw characters (excluding HTML tags)
    text_content = soup.get_text()
    char_count = len(text_content)

    # Count structural elements
    para_count = len(soup.find_all("p"))
    h2_count = len(soup.find_all("h2"))
    h3_count = len(soup.find_all("h3"))
    blockquote_count = len(soup.find_all("blockquote"))
    image_count = len(soup.find_all("img"))

    # Apply compound cost formula
    effective_size = (
        char_count
        + (para_count * Config.KINDLE_COST_PARA)
        + (h2_count * Config.KINDLE_COST_H2)
        + (h3_count * Config.KINDLE_COST_H3)
        + (blockquote_count * Config.KINDLE_COST_BLOCKQUOTE)
        + (image_count * Config.KINDLE_COST_IMAGE)
    )

    return effective_size

# Cache for paginated documents
pagination_cache: dict[str, Tuple[List[str], int]] = {}


def paginate_html(html: str, doc_id: str) -> Tuple[List[str], int]:
    """
    Paginate HTML content into Kindle-sized pages using calibrated effective size model.

    Uses compound cost formula that accounts for vertical space of different
    HTML elements, not just character count. Preserves block integrity - entire
    block-level elements are kept together even if they exceed the budget.

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

    # Paginate blocks using compound cost model
    pages: List[List[Tag]] = []
    current_page: List[Tag] = []
    current_size = 0

    for block in blocks:
        # Calculate effective size of this single block
        block_html = str(block)
        block_size = calculate_effective_size(block_html)

        # Handle images
        if block.name == "img":
            if Config.IMAGE_SEPARATE_PAGE:
                # Close current page if it has content
                if current_page:
                    pages.append(current_page)
                    current_page = []
                    current_size = 0

                # Image on its own page
                pages.append([block])
                continue
            else:
                # Treat image like a block
                pass

        # Check if adding this block would exceed budget
        if current_size > 0 and current_size + block_size > Config.KINDLE_PAGE_BUDGET:
            # Start new page (only if current_page is not empty)
            pages.append(current_page)
            current_page = [block]
            current_size = block_size
        else:
            # Add block to current page
            current_page.append(block)
            current_size += block_size

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
