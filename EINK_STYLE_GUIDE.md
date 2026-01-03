# E-Ink Display Style Guide

This document defines the styling and formatting rules for templates and content optimized for e-ink displays (specifically Kindle devices). All templates must follow these guidelines to ensure optimal readability and performance on e-ink screens.

## Typography Rules

### Text Alignment and Spacing

```css
body {
    /* Justified text with automatic hyphenation */
    text-align: justify;
    hyphens: auto;
    -webkit-hyphens: auto;
    text-justify: inter-word;

    /* Enhanced character spacing for e-ink clarity */
    letter-spacing: 0.015em;

    /* Line height for comfortable reading */
    line-height: 1.5;
}
```

**Rationale**:
- Kindle's "Enhanced Typesetting" uses automatic hyphenation to prevent large gaps in justified text
- E-ink displays benefit from slightly increased letter spacing (0.015em) for improved clarity
- Inter-word justification prevents awkward spacing and improves readability

**Sources**:
- [Enhanced Typesetting - Kindle Direct Publishing](https://kdp.amazon.com/en_US/help/topic/G202087570)
- [Amazon finally fixes the Kindle's text justification](https://kottke.org/15/05/amazon-finally-fixes-the-kindles-text-justification)

### Font Rendering Optimization

```css
body {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
}
```

**Rationale**:
- Antialiased rendering produces sharper text on e-ink displays
- `optimizeLegibility` enables kerning and ligatures for professional typography
- Research shows these settings improve legibility on low-DPI e-ink screens

**Sources**:
- [Developing a Typeface for Low Resolution E-Ink Displays](https://www.researchgate.net/publication/324671274_Developing_a_Typeface_for_Low_Resolution_E-Ink_Displays)

## Color and Contrast Rules

### Pure Black and White Only

E-ink displays have limited grayscale range (16 levels on most Kindles). **Use pure black and white exclusively** for maximum contrast.

```css
:root {
    /* Light mode: pure black on white */
    --bg-color: #ffffff;
    --text-color: #000000;
    --link-color: #000000;
    --border-color: #000000;
    /* ... all other colors: #000000 */
}

:root.dark {
    /* Dark mode: pure white on black */
    --bg-color: #000000;
    --text-color: #ffffff;
    --link-color: #ffffff;
    --border-color: #ffffff;
    /* ... all other colors: #ffffff */
}
```

**Rules**:
- ✅ **DO** use `#000000` (pure black) and `#ffffff` (pure white)
- ❌ **DON'T** use grays like `#333`, `#666`, `#999`, `#ccc`, etc.
- ❌ **DON'T** use colors like blue, red, etc. (they render as grays on e-ink)
- ✅ **DO** use underlines, borders, or font styling to differentiate elements instead of color

**Rationale**:
- E-ink displays work best with 10:1+ contrast ratios
- Pure black/white provides 21:1 contrast ratio (maximum possible)
- Grays reduce contrast and can appear muddy on e-ink screens
- Pearl displays have 10:1 contrast; Carta displays have 15:1 contrast

**Sources**:
- [Building websites that work on an e-ink Kindle](https://gomakethings.com/building-websites-that-work-on-an-e-ink-kindle/)
- [Optimizing KOReader for Comfortable Reading](https://www.ereadersforum.com/blog/optimizing-koreader-for-comfortable-reading-on-any-e-reader/)

### Visual Hierarchy Without Color

Use these techniques to create visual distinction:

```css
/* Links: use underlines instead of color */
a {
    color: var(--text-color);  /* Same as body text */
    text-decoration: underline;
}

/* Emphasis: use borders instead of backgrounds */
blockquote {
    border-left: 3px solid var(--border-color);
    padding-left: 1em;
}

/* Metadata: use font size/style instead of gray text */
.article-meta {
    font-size: 0.9em;
    font-style: italic;  /* Optional */
}
```

## Screen Refresh Logic

E-ink displays accumulate "ghosting" (faint traces of previous text) with partial refreshes. Kindle performs full screen refreshes periodically to clear this.

### Refresh Intervals

```javascript
// Detect dark mode
var isDarkMode = document.documentElement.classList.contains('dark');

// Set refresh interval based on mode
var REFRESH_INTERVAL = isDarkMode ? 8 : 6;
```

**Rules**:
- Light mode: refresh every **6 page turns**
- Dark mode: refresh every **8 page turns**
- Dark mode shows less ghosting, so can wait longer between refreshes

**Rationale**: Kindle does full refresh every 5-6 page turns. Dark backgrounds mask ghosting better than light backgrounds.

**Sources**:
- [Why Kindle Screens Flash and How to Turn it On and Off](https://blog.the-ebook-reader.com/2018/01/03/heres-why-kindle-screens-flash-and-how-to-turn-it-on-and-off/)

### Flash Sequence

```javascript
function flashScreen() {
    // Flash pattern: white → black → restore (or inverted for dark mode)
    var firstFlash = isDarkMode ? '#000000' : '#FFFFFF';
    var secondFlash = isDarkMode ? '#FFFFFF' : '#000000';

    // Each flash: 100ms duration
    document.body.style.backgroundColor = firstFlash;
    document.body.style.color = firstFlash;

    setTimeout(function() {
        document.body.style.backgroundColor = secondFlash;
        document.body.style.color = secondFlash;

        setTimeout(function() {
            // Restore CSS variables
            document.body.style.backgroundColor = '';
            document.body.style.color = '';
        }, 100);
    }, 100);
}
```

**Rules**:
- Total flash duration: **200ms** (100ms per flash)
- Light mode: white → black → restore
- Dark mode: black → white → restore (inverted)
- Flash on initial article load
- Flash every N scrolls/page turns

### Scroll Tracking

Use `sessionStorage` to track page turns within an article:

```javascript
function handleScroll(amount) {
    window.scrollBy(0, amount);

    var scrollCount = parseInt(sessionStorage.getItem('scrollCount') || '0');
    scrollCount++;

    if (scrollCount >= REFRESH_INTERVAL) {
        flashScreen();
        scrollCount = 0;
    }

    sessionStorage.setItem('scrollCount', scrollCount.toString());
}
```

## Font Guidelines

**Current standard**: Merriweather (serif font from Google Fonts)

```html
<link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap" rel="stylesheet">
```

```css
body {
    font-family: "Merriweather", Georgia, serif;
    font-size: 18px;
}
```

**Fallback hierarchy**: Merriweather → Georgia → system serif

**Note**: Research shows serif fonts (Georgia, Merriweather) are more legible than Times New Roman on e-ink displays. Sans-serif fonts (Verdana, Arial) can also work well but serif is preferred for long-form reading.

**Sources**:
- [Best Fonts for eBooks in 2025](https://www.editionguard.com/learn/best-fonts-e-books/)

## Image Handling

**Current policy**: Images are allowed but not optimized.

**Future considerations** (not yet implemented):
- Convert images to grayscale
- Apply dithering (Floyd-Steinberg or Atkinson algorithm)
- Boost contrast by 20-30%
- Scale to display resolution

**Sources**:
- [Preparing Graphics for E-Ink Displays - Adafruit](https://learn.adafruit.com/preparing-graphics-for-e-ink-displays)
- [E Ink display APP, ePaper Image Dithering](https://www.good-display.com/news/194.html)

## Performance Rules

### Minimize HTTP Requests

```html
<!-- ✅ DO: Inline styles in <style> block -->
<style>
    body { ... }
</style>

<!-- ❌ DON'T: External stylesheet -->
<link rel="stylesheet" href="/static/style.css">
```

**Rationale**: E-ink displays have slow refresh rates. Minimize requests to reduce perceived latency.

### No Animations or Transitions

```css
/* ❌ DON'T use animations */
.element {
    transition: all 0.3s ease;  /* NO */
    animation: fadeIn 1s;       /* NO */
}

/* ✅ DO use instant changes */
.element {
    /* No transitions */
}
```

**Rationale**: E-ink displays have slow refresh rates (~100-250ms). Animations look janky and waste battery.

## Template Checklist

When creating new templates, verify:

- [ ] Pure black/white color scheme (no grays or colors)
- [ ] Text is justified with hyphenation enabled
- [ ] Letter spacing is 0.015em
- [ ] Font rendering optimizations are applied
- [ ] All styles are inline (no external CSS)
- [ ] No animations or transitions
- [ ] Screen flash logic is implemented for long content
- [ ] Dark mode class (`dark`) toggles black/white correctly

## Testing Recommendations

1. **Test on actual Kindle device** - Simulator/desktop won't show e-ink artifacts
2. **Test both light and dark modes** - Verify contrast and readability
3. **Scroll through long articles** - Verify screen refresh triggers correctly
4. **Check ghosting** - Ensure refreshes clear previous text adequately
5. **Verify tap zones** - Ensure scrolling works on left/right taps

## References

- [Enhanced Typesetting - Kindle Direct Publishing](https://kdp.amazon.com/en_US/help/topic/G202087570)
- [Building websites that work on an e-ink Kindle](https://gomakethings.com/building-websites-that-work-on-an-e-ink-kindle/)
- [Optimizing KOReader for Comfortable Reading](https://www.ereadersforum.com/blog/optimizing-koreader-for-comfortable-reading-on-any-e-reader/)
- [Why Kindle Screens Flash and How to Turn it On and Off](https://blog.the-ebook-reader.com/2018/01/03/heres-why-kindle-screens-flash-and-how-to-turn-it-on-and-off/)
- [Developing a Typeface for Low Resolution E-Ink Displays](https://www.researchgate.net/publication/324671274_Developing_a_Typeface_for_Low_Resolution_E-Ink_Displays)
- [Best Fonts for eBooks in 2025](https://www.editionguard.com/learn/best-fonts-e-books/)
- [Preparing Graphics for E-Ink Displays - Adafruit](https://learn.adafruit.com/preparing-graphics-for-e-ink-displays)

---

**Last updated**: January 2, 2026
