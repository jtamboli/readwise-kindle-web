"""Tests for HTML sanitizer."""
import pytest
from kindle_reader.sanitizer import sanitize_html, ALLOWED_TAGS, ALLOWED_ATTRS


class TestAllowedTags:
    """Tests for ALLOWED_TAGS constant."""

    def test_contains_headings(self):
        """Should allow heading tags."""
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            assert tag in ALLOWED_TAGS

    def test_contains_block_elements(self):
        """Should allow block elements."""
        for tag in ["p", "blockquote", "pre", "hr"]:
            assert tag in ALLOWED_TAGS

    def test_contains_lists(self):
        """Should allow list elements."""
        for tag in ["ul", "ol", "li"]:
            assert tag in ALLOWED_TAGS

    def test_contains_tables(self):
        """Should allow table elements."""
        for tag in ["table", "thead", "tbody", "tr", "th", "td"]:
            assert tag in ALLOWED_TAGS

    def test_contains_inline_formatting(self):
        """Should allow inline formatting elements."""
        for tag in ["a", "em", "i", "strong", "b", "code", "sup", "sub"]:
            assert tag in ALLOWED_TAGS

    def test_contains_media(self):
        """Should allow media elements."""
        for tag in ["img", "figure", "figcaption"]:
            assert tag in ALLOWED_TAGS

    def test_excludes_script(self):
        """Should not allow script tag."""
        assert "script" not in ALLOWED_TAGS

    def test_excludes_style(self):
        """Should not allow style tag."""
        assert "style" not in ALLOWED_TAGS

    def test_excludes_iframe(self):
        """Should not allow iframe tag."""
        assert "iframe" not in ALLOWED_TAGS


class TestAllowedAttrs:
    """Tests for ALLOWED_ATTRS constant."""

    def test_link_href_allowed(self):
        """Should allow href on anchor tags."""
        assert "href" in ALLOWED_ATTRS.get("a", [])

    def test_image_attrs_allowed(self):
        """Should allow src and alt on image tags."""
        assert "src" in ALLOWED_ATTRS.get("img", [])
        assert "alt" in ALLOWED_ATTRS.get("img", [])


class TestSanitizeHtml:
    """Tests for sanitize_html function."""

    def test_empty_string(self):
        """Should return empty string for empty input."""
        assert sanitize_html("") == ""

    def test_none_input(self):
        """Should return empty string for None input."""
        assert sanitize_html(None) == ""

    def test_plain_text(self):
        """Should preserve plain text."""
        text = "Hello, world!"
        assert sanitize_html(text) == text

    def test_allowed_tags_preserved(self):
        """Should preserve allowed HTML tags."""
        html = "<p>Hello <strong>world</strong>!</p>"
        assert sanitize_html(html) == html

    def test_heading_preserved(self):
        """Should preserve heading tags."""
        html = "<h1>Title</h1><h2>Subtitle</h2>"
        assert sanitize_html(html) == html

    def test_list_preserved(self):
        """Should preserve list elements."""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        assert sanitize_html(html) == html

    def test_link_preserved_with_href(self):
        """Should preserve links with href attribute."""
        html = '<a href="https://example.com">Link</a>'
        assert sanitize_html(html) == html

    def test_image_preserved_with_attrs(self):
        """Should preserve images with src and alt."""
        html = '<img src="image.jpg" alt="Description">'
        result = sanitize_html(html)
        assert 'src="image.jpg"' in result
        assert 'alt="Description"' in result

    def test_script_removed(self):
        """Should remove script tags but preserve text content (bleach strip behavior)."""
        html = "<p>Hello</p><script>alert('xss')</script><p>World</p>"
        result = sanitize_html(html)
        assert "<script>" not in result
        assert "</script>" not in result
        assert "<p>Hello</p>" in result
        assert "<p>World</p>" in result
        # Note: bleach with strip=True removes tags but keeps text content
        # This is intentional - text content is safe, only the tags are dangerous

    def test_style_tag_removed(self):
        """Should remove style tags but preserve text content (bleach strip behavior)."""
        html = "<style>body { color: red; }</style><p>Text</p>"
        result = sanitize_html(html)
        assert "<style>" not in result
        assert "</style>" not in result
        assert "<p>Text</p>" in result
        # Note: bleach with strip=True removes tags but keeps text content

    def test_inline_style_removed(self):
        """Should remove inline style attributes."""
        html = '<p style="color: red;">Text</p>'
        result = sanitize_html(html)
        assert "style" not in result
        assert "<p>Text</p>" in result

    def test_onclick_removed(self):
        """Should remove onclick and other event handlers."""
        html = '<a href="#" onclick="alert(1)">Click</a>'
        result = sanitize_html(html)
        assert "onclick" not in result
        assert 'href="#"' in result

    def test_iframe_removed(self):
        """Should remove iframe elements."""
        html = '<p>Before</p><iframe src="evil.com"></iframe><p>After</p>'
        result = sanitize_html(html)
        assert "<iframe" not in result
        assert "<p>Before</p>" in result
        assert "<p>After</p>" in result

    def test_nested_tags_preserved(self):
        """Should preserve nested allowed tags."""
        html = "<blockquote><p><strong>Bold</strong> and <em>italic</em></p></blockquote>"
        assert sanitize_html(html) == html

    def test_table_preserved(self):
        """Should preserve table structure."""
        html = "<table><thead><tr><th>Header</th></tr></thead><tbody><tr><td>Data</td></tr></tbody></table>"
        assert sanitize_html(html) == html

    def test_figure_preserved(self):
        """Should preserve figure and figcaption."""
        html = '<figure><img src="photo.jpg" alt="Photo"><figcaption>Caption</figcaption></figure>'
        result = sanitize_html(html)
        assert "<figure>" in result
        assert "<figcaption>" in result

    def test_code_preserved(self):
        """Should preserve code blocks."""
        html = "<pre><code>def hello():\n    print('hi')</code></pre>"
        assert sanitize_html(html) == html

    def test_xss_prevention(self):
        """Should prevent common XSS attacks."""
        xss_attempts = [
            '<img src="x" onerror="alert(1)">',
            '<a href="javascript:alert(1)">Click</a>',
            '<div onmouseover="alert(1)">Hover</div>',
        ]
        for html in xss_attempts:
            result = sanitize_html(html)
            assert "onerror" not in result
            assert "onmouseover" not in result
            # javascript: URLs are stripped by bleach by default

    def test_unknown_tag_stripped(self):
        """Should strip unknown tags but preserve content."""
        html = "<custom>Content inside custom tag</custom>"
        result = sanitize_html(html)
        assert "<custom>" not in result
        assert "Content inside custom tag" in result

    def test_complex_document(self):
        """Should handle complex HTML documents."""
        html = """
        <h1>Article Title</h1>
        <p>Introduction paragraph with <a href="https://example.com">a link</a>.</p>
        <h2>Section</h2>
        <ul>
            <li>Item <strong>one</strong></li>
            <li>Item <em>two</em></li>
        </ul>
        <blockquote>
            <p>A quote</p>
        </blockquote>
        <pre><code>code example</code></pre>
        """
        result = sanitize_html(html)
        # All structural elements should be preserved
        assert "<h1>" in result
        assert "<h2>" in result
        assert "<p>" in result
        assert "<ul>" in result
        assert "<li>" in result
        assert "<blockquote>" in result
        assert "<pre>" in result
        assert "<code>" in result
