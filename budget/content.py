"""Content loading and HTML generation."""
import json
import random
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

from config import (
    READWISE_JSON_PATH,
    TEST_IMAGES_DIR,
    MIN_CHARS_FOR_CONTENT,
    get_test_images,
)


# Global content pool (loaded once)
_content_pool: Optional[List[Dict]] = None


def load_content_pool() -> List[Dict]:
    """Load readwise.json into memory."""
    global _content_pool

    if _content_pool is None:
        with open(READWISE_JSON_PATH, "r") as f:
            _content_pool = json.load(f)

    return _content_pool


def select_content(target_chars: int) -> str:
    """
    Select random article and extract approximately target_chars of text.
    Returns plain text (paragraphs separated by double newlines).
    """
    pool = load_content_pool()

    # Try to find an article with content
    max_attempts = 10
    for _ in range(max_attempts):
        article = random.choice(pool)

        # Try to extract text from various fields
        text = _extract_text_from_article(article)

        if text and len(text) >= MIN_CHARS_FOR_CONTENT:
            # Truncate to approximately target length
            if len(text) > target_chars:
                # Find a good break point (end of sentence or paragraph)
                text = _truncate_at_sentence(text, target_chars)

            return text

    # Fallback: generate lorem ipsum
    return _generate_lorem_ipsum(target_chars)


def _extract_text_from_article(article: Dict) -> str:
    """Extract text from article, trying various fields."""
    # Try html_content first
    if article.get("html_content"):
        soup = BeautifulSoup(article["html_content"], "html.parser")
        paragraphs = []
        for p in soup.find_all(["p", "blockquote", "li"]):
            text = p.get_text(strip=True)
            if text and len(text) > 20:  # Skip very short paragraphs
                paragraphs.append(text)
        if paragraphs:
            return "\n\n".join(paragraphs)

    # Try summary
    if article.get("summary"):
        return article["summary"]

    # Try title as last resort
    if article.get("title"):
        return article["title"] + "\n\n" + (article.get("notes", "") or "")

    return ""


def _truncate_at_sentence(text: str, target_chars: int) -> str:
    """Truncate text at approximately target_chars, ending at sentence boundary."""
    if len(text) <= target_chars:
        return text

    # Find the last sentence ending before target
    truncated = text[:target_chars]

    # Look for sentence endings
    for delimiter in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
        last_pos = truncated.rfind(delimiter)
        if last_pos > target_chars * 0.8:  # At least 80% of target
            return text[: last_pos + 1]

    # No good sentence boundary, just cut at word boundary
    last_space = truncated.rfind(" ")
    if last_space > 0:
        return text[:last_space]

    return truncated


def _generate_lorem_ipsum(target_chars: int) -> str:
    """Generate lorem ipsum text as fallback."""
    lorem = """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.

Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.

Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo.

Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt."""

    # Repeat until we have enough
    result = []
    while len("\n\n".join(result)) < target_chars:
        result.append(lorem)

    return "\n\n".join(result)[: target_chars]


def render_page(
    composition: Dict[str, int], costs: Dict[str, int], trial_id: str
) -> Tuple[str, int]:
    """
    Render HTML page based on composition spec.

    Takes composition dict and structures raw text into HTML
    with specified numbers of paragraphs, headers, images, etc.

    Returns: (html_content, effective_size)
    """
    from calibration import calculate_effective_size

    # Get raw text
    text = select_content(composition["chars"])

    # Split into sentences for structuring
    sentences = _split_into_sentences(text)

    # Build HTML elements
    elements = []

    # Generate paragraphs
    if composition["para"] > 0 and sentences:
        sentences_per_para = max(1, len(sentences) // composition["para"])
        for i in range(composition["para"]):
            start = i * sentences_per_para
            end = start + sentences_per_para
            para_sentences = sentences[start:end]

            if para_sentences:
                para_text = " ".join(para_sentences)
                elements.append(f"<p>{para_text}</p>")

    # If no sentences left, add at least one paragraph with the text
    if not elements:
        elements.append(f"<p>{text}</p>")

    # Inject H2 headers at distributed positions
    if composition["h2"] > 0:
        h2_positions = _distribute_positions(len(elements), composition["h2"])
        for idx, pos in enumerate(sorted(h2_positions, reverse=True)):
            if pos < len(elements):
                elements.insert(pos, f"<h2>Section {idx + 1}</h2>")

    # Inject H3 headers
    if composition["h3"] > 0:
        h3_positions = _distribute_positions(len(elements), composition["h3"])
        for idx, pos in enumerate(sorted(h3_positions, reverse=True)):
            if pos < len(elements):
                elements.insert(pos, f"<h3>Subsection {idx + 1}</h3>")

    # Convert some paragraphs to blockquotes
    if composition["blockquote"] > 0:
        para_indices = [
            i for i, elem in enumerate(elements) if elem.startswith("<p>")
        ]
        if para_indices:
            # Select random paragraphs to convert
            num_to_convert = min(composition["blockquote"], len(para_indices))
            selected = random.sample(para_indices, num_to_convert)

            for idx in selected:
                elements[idx] = (
                    elements[idx]
                    .replace("<p>", "<blockquote><p>", 1)
                    .replace("</p>", "</p></blockquote>", 1)
                )

    # Inject images at distributed positions
    if composition["image"] > 0:
        test_images = get_test_images()
        if test_images:
            img_positions = _distribute_positions(len(elements), composition["image"])
            for idx, pos in enumerate(sorted(img_positions, reverse=True)):
                img_file = test_images[idx % len(test_images)]
                img_tag = f'<img src="/static/test_images/{img_file}" alt="Test image {idx + 1}" />'
                if pos < len(elements):
                    elements.insert(pos, img_tag)

    # Calculate actual effective size
    effective_size = calculate_effective_size(composition, costs)

    # Return just the content (metadata will be rendered in template after navigation)
    content_html = "\n".join(elements)

    return content_html, effective_size


def _split_into_sentences(text: str) -> List[str]:
    """Simple sentence splitter."""
    # Split on period followed by space or newline
    sentences = []
    for part in text.replace("\n\n", " ").split(". "):
        if part.strip():
            # Clean up extra whitespace
            sentence = " ".join(part.split())
            if sentence:
                sentences.append(sentence + ".")

    return sentences


def _distribute_positions(total: int, count: int) -> List[int]:
    """Distribute count items evenly across total positions."""
    if count >= total:
        return list(range(total))

    if count == 0:
        return []

    # Distribute evenly
    step = total // (count + 1)
    return [step * (i + 1) for i in range(count)]
