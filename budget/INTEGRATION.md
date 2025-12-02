# Integration Guide: Applying Calibrated Values to Parent App

This guide explains how to integrate the calibrated page-breaking parameters from the budget calibration tool into the main Readwise Kindle web reader application.

## Prerequisites

Before beginning integration, ensure:
- ✅ Calibration has completed (Phase 3 finished)
- ✅ `/status` shows "Completed" timestamp
- ✅ Multiple "just right" feedbacks in recent trials

## Step 1: Export Calibrated Values

### On Desktop

Visit the export endpoint:
```bash
http://localhost:8080/export
```

You'll receive JSON like this:
```json
{
  "budget": 1850,
  "costs": {
    "para": 65,
    "h2": 135,
    "h3": 95,
    "blockquote": 75,
    "image": 420
  },
  "calibration_complete": true,
  "total_trials": 42
}
```

**Save this output** - you'll need these values for the next steps.

### Verify Values Are Reasonable

Before proceeding, sanity-check the calibrated values:

- **Budget**: Should be 800-3500 (typical: 1500-2500)
- **Para cost**: Should be 20-150 (typical: 50-100)
- **H2 cost**: Should be 60-250 (typical: 100-180)
- **H3 cost**: Should be 40-180 (typical: 70-130)
- **Blockquote cost**: Should be 30-150 (typical: 50-100)
- **Image cost**: Should be 150-800 (typical: 300-500)

If values are outside these ranges or seem extreme, consider re-running calibration.

## Step 2: Update Parent App Configuration

### 2.1 Locate Parent Config

The main app config is at:
```
../app/config.py
```
(relative to the budget tool directory)

### 2.2 Add Calibrated Constants

Add these constants to `../app/config.py`:

```python
# ============================================================================
# KINDLE PAGE LAYOUT - CALIBRATED VALUES
# ============================================================================
# These values were empirically determined using the budget calibration tool
# Calibrated: [INSERT DATE]
# Device: Kindle Paperwhite (or your device)
# Total calibration trials: [INSERT total_trials FROM EXPORT]

# Maximum effective size for a single page
# This is the target threshold - pages should not exceed this value
KINDLE_PAGE_BUDGET = 1850  # REPLACE with your "budget" value

# Cost multipliers for different HTML elements
# These represent the vertical space overhead beyond raw character count
KINDLE_COST_PARA = 65         # REPLACE with your "costs.para" value
KINDLE_COST_H2 = 135          # REPLACE with your "costs.h2" value
KINDLE_COST_H3 = 95           # REPLACE with your "costs.h3" value
KINDLE_COST_BLOCKQUOTE = 75   # REPLACE with your "costs.blockquote" value
KINDLE_COST_IMAGE = 420       # REPLACE with your "costs.image" value

# Compound cost formula:
# effective_size = chars + (para_count × PARA_COST) + (h2_count × H2_COST) +
#                  (h3_count × H3_COST) + (blockquote_count × BQ_COST) +
#                  (image_count × IMAGE_COST)
```

### 2.3 Example with Real Values

If your export showed:
```json
{
  "budget": 2150,
  "costs": {
    "para": 82,
    "h2": 156,
    "h3": 118,
    "blockquote": 88,
    "image": 445
  }
}
```

Then add to config:
```python
KINDLE_PAGE_BUDGET = 2150
KINDLE_COST_PARA = 82
KINDLE_COST_H2 = 156
KINDLE_COST_H3 = 118
KINDLE_COST_BLOCKQUOTE = 88
KINDLE_COST_IMAGE = 445
```

## Step 3: Update Paginator Logic

### 3.1 Locate Paginator File

The pagination logic is at:
```
../app/paginator.py
```

### 3.2 Add Effective Size Calculator

Add this function to `paginator.py`:

```python
from bs4 import BeautifulSoup
from app.config import (
    KINDLE_PAGE_BUDGET,
    KINDLE_COST_PARA,
    KINDLE_COST_H2,
    KINDLE_COST_H3,
    KINDLE_COST_BLOCKQUOTE,
    KINDLE_COST_IMAGE,
)


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
        char_count +
        (para_count * KINDLE_COST_PARA) +
        (h2_count * KINDLE_COST_H2) +
        (h3_count * KINDLE_COST_H3) +
        (blockquote_count * KINDLE_COST_BLOCKQUOTE) +
        (image_count * KINDLE_COST_IMAGE)
    )

    return effective_size
```

### 3.3 Update Page Breaking Logic

Find your existing page-breaking function (e.g., `paginate_article()` or similar) and replace simple character counting with effective size calculation.

**Before (simple character counting):**
```python
def paginate_article(html_content: str, max_chars: int = 2000) -> List[str]:
    """Split article into pages."""
    pages = []
    current_page = []
    current_chars = 0

    soup = BeautifulSoup(html_content, "html.parser")
    blocks = soup.find_all(["p", "h2", "h3", "blockquote", "img"])

    for block in blocks:
        block_text = block.get_text(strip=True)
        block_chars = len(block_text)

        if current_chars + block_chars > max_chars:
            # Start new page
            pages.append("".join(str(b) for b in current_page))
            current_page = [block]
            current_chars = block_chars
        else:
            current_page.append(block)
            current_chars += block_chars

    # Add final page
    if current_page:
        pages.append("".join(str(b) for b in current_page))

    return pages
```

**After (compound cost model):**
```python
def paginate_article(html_content: str) -> List[str]:
    """
    Split article into pages using calibrated effective size model.

    Uses compound cost formula that accounts for vertical space of different
    HTML elements, not just character count.
    """
    pages = []
    current_page = []
    current_size = 0

    soup = BeautifulSoup(html_content, "html.parser")
    blocks = soup.find_all(["p", "h2", "h3", "blockquote", "img"])

    for block in blocks:
        # Calculate effective size of this single block
        block_html = str(block)
        block_size = calculate_effective_size(block_html)

        # Check if adding this block would exceed budget
        if current_size + block_size > KINDLE_PAGE_BUDGET and current_page:
            # Start new page (only if current_page is not empty)
            pages.append("".join(str(b) for b in current_page))
            current_page = [block]
            current_size = block_size
        else:
            # Add block to current page
            current_page.append(block)
            current_size += block_size

    # Add final page
    if current_page:
        pages.append("".join(str(b) for b in current_page))

    return pages
```

### 3.4 Important Implementation Notes

**Block Integrity:** The paginator should NEVER split individual blocks (paragraphs, headers, etc.). Each block is atomic - if a single paragraph's effective size exceeds the budget, it should still appear as a complete page by itself.

**Cumulative Calculation:** When building up a page, you can either:
1. Calculate effective size of the cumulative HTML (`calculate_effective_size(current_page_html)`)
2. Add up individual block sizes (faster but less accurate due to element interaction)

Option 1 is more accurate; Option 2 is a reasonable approximation if performance matters.

**Edge Cases:**
- Empty pages: Skip them
- Very large blocks: Allow single block to exceed budget rather than split
- Images: Ensure image tags are preserved with proper src paths

## Step 4: Test the Integration

### 4.1 Local Testing

1. **Start the parent app** with updated config and paginator
2. **Browse an article** on desktop browser first
3. **Check page breaks** occur at reasonable locations
4. **Verify no split blocks** - each paragraph, header, quote should be intact

### 4.2 Kindle Testing

1. **Access on Kindle** via Tailscale or your deployment method
2. **Read through several articles** with different content types:
   - Text-heavy articles (many paragraphs)
   - Articles with headers (h2, h3)
   - Articles with blockquotes
   - Articles with images (if available)
3. **Verify pages fit screen** without scrolling to see navigation
4. **Check edge cases**:
   - Very short articles (single page)
   - Very long articles (many pages)
   - Articles with large images

### 4.3 Validation Checklist

- [ ] Pages display without vertical scrolling
- [ ] Navigation links are visible at bottom of each page
- [ ] No blocks are split across pages
- [ ] Page numbers are correct (Page X of Y)
- [ ] Next/Previous navigation works
- [ ] Images display properly (if using images)
- [ ] Different content types paginate correctly

## Step 5: Fine-Tuning (If Needed)

If after integration you find:

**Pages consistently too large** (need scrolling):
- Reduce `KINDLE_PAGE_BUDGET` by 10-15%
- Re-test

**Pages consistently too small** (excess whitespace):
- Increase `KINDLE_PAGE_BUDGET` by 10-15%
- Re-test

**Specific elements cause issues** (e.g., images always overflow):
- Increase that element's cost multiplier (e.g., `KINDLE_COST_IMAGE`)
- Re-test

**Major adjustment needed:**
- Re-run calibration with the budget tool
- The tool is designed for iterative refinement

## Step 6: Document Your Deployment

Add a comment to your config noting:
```python
# Calibration Info:
# - Date: 2024-12-02
# - Device: Kindle Paperwhite 11th Gen
# - Total trials: 42
# - Notes: Calibrated with standard font size, no zoom
```

This helps if you need to recalibrate later or deploy to different devices.

## Troubleshooting

### Issue: Pagination worse than before

**Cause:** Calibrated values might be for wrong device or font settings

**Solution:** Re-run calibration ensuring consistent Kindle settings throughout

### Issue: Images cause overflow

**Cause:** Image cost might be too low, or images are larger than test images

**Solution:**
1. Increase `KINDLE_COST_IMAGE` by 20-30%
2. Or implement image resizing in the parent app
3. Or re-run calibration with representative images

### Issue: Some pages still overflow

**Cause:** Edge cases not covered in calibration (e.g., many headers, nested blockquotes)

**Solution:**
1. Add a safety margin: reduce budget by 10%
2. Add max element limits to paginator (e.g., max 3 images per page)
3. Re-run calibration with more diverse content

## Appendix: Understanding the Cost Model

The compound cost formula models how much vertical space each element type consumes:

```
effective_size = base_chars + overhead_from_elements
```

Where:
- **base_chars**: Raw text characters
- **overhead_from_elements**: Sum of (count × cost) for each element type

**Example calculation:**

HTML content:
```html
<p>First paragraph with 150 chars...</p>
<p>Second paragraph with 180 chars...</p>
<h2>A header</h2>
<p>Third paragraph with 120 chars...</p>
<img src="photo.jpg" />
```

With calibrated costs:
- Budget: 2000
- Para cost: 70
- H2 cost: 140
- Image cost: 400

Calculation:
```
chars = 150 + 180 + 8 + 120 = 458
paras = 3 × 70 = 210
h2s = 1 × 140 = 140
images = 1 × 400 = 400

effective_size = 458 + 210 + 140 + 400 = 1208
```

Since 1208 < 2000, this content fits on one page.

## Next Steps

After successful integration:
1. Monitor user feedback (if any)
2. Consider calibrating for different devices if needed
3. Document calibration values in version control
4. Set reminder to recalibrate if Kindle firmware updates affect rendering

---

**Questions or Issues?**

Refer to the budget tool README.md for recalibration instructions, or review the calibration_state.json for historical trial data.
