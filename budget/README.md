# Kindle Display Calibration Tool

A FastAPI-based calibration tool to empirically determine optimal page-breaking parameters for displaying Readwise content on a Kindle web browser.

## Overview

This tool uses a three-phase binary search approach to calibrate:
1. **Phase 1 (Budget)**: Overall effective size threshold (~8-12 trials)
2. **Phase 2 (Costs)**: Individual cost multipliers for paragraphs, headers, images, blockquotes (~15-25 trials per cost)
3. **Phase 3 (Budget Recalibration)**: Re-calibrate budget with the new cost values (~5-8 trials)

Phase 3 automatically triggers after all costs lock, because the budget from Phase 1 was calibrated with default costs and becomes invalid when costs change in Phase 2.

**Compound Cost Model:**
```
effective_size = chars + (para_count × PARA_COST) + (h2_count × H2_COST) +
                 (h3_count × H3_COST) + (blockquote_count × BQ_COST) +
                 (image_count × IMAGE_COST)
```

## Setup

### 1. Add Test Images (Optional)

Copy 3-5 test images (JPG or PNG) to `static/test_images/` for image calibration:

```bash
# Example: Copy some sample images
cp ~/Pictures/test-*.jpg static/test_images/
```

If no images are provided, image calibration will be skipped.

## Running the Server

The server uses inline script dependencies (PEP 723), so you can run it directly with `uv`:

```bash
cd /Volumes/Burpleson/Source/readwise-kindle-web/budget
uv run server.py
```

`uv` will automatically install the required dependencies on first run.

**Note:** The `requirements.txt` file is kept for reference, but is not needed when using `uv run`.

The server will:
- Auto-select an available port (8080-8090)
- Display the Tailscale funnel command to run
- Show the URL to access on Kindle

**Example output:**
```
======================================================================
Kindle Calibration Server
======================================================================
Server starting on 0.0.0.0:8080
Local access: http://localhost:8080

Tailscale funnel command (run in another terminal):
  tailscale funnel --https 10000 8080

Then access on Kindle:
  https://your-machine.ts.net:10000/
======================================================================
```

## Exposing via Tailscale

In another terminal, run the command shown by the server (the port will match what the server selected):

```bash
tailscale funnel --https 10000 8080
```

This exposes your local server on HTTPS port 10000 via Tailscale, accessible from your Kindle browser.

## Calibration Workflow

### 1. Access on Kindle
- Open Kindle browser
- Navigate to `https://your-machine.ts.net:10000/`
- Bookmark for easy access

### 2. Provide Feedback
For each trial page:
- **Too Big**: Had to scroll to see all content
- **Just Right**: Content fits perfectly without scrolling
- **Too Small**: Extra white space at bottom

### 3. Monitor Progress
On your desktop, visit `http://localhost:8080/status` to see:
- Current phase and convergence progress
- Budget and cost multiplier ranges
- Recent trial history

### 4. Export Results
When calibration completes (all costs converged), visit:
```
http://localhost:8080/export
```

This returns JSON with calibrated values:
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
  "total_trials": 35
}
```

## Routes

- `GET /` - Current trial page (Kindle view)
- `GET /feedback/<trial_id>/<response>` - Submit feedback
- `GET /status` - Calibration dashboard (desktop view)
- `GET /export` - Export calibrated config as JSON
- `GET /reset` - Reset calibration state
- `GET /health` - Health check

## Integration with Parent App

After calibration, update the main Readwise Kindle app:

### 1. Update config.py

Add calibrated values to `../app/config.py`:

```python
# Calibrated values from budget tool
KINDLE_PAGE_EFFECTIVE_SIZE_BUDGET = 1850
KINDLE_COST_PARA = 65
KINDLE_COST_H2 = 135
KINDLE_COST_H3 = 95
KINDLE_COST_BLOCKQUOTE = 75
KINDLE_COST_IMAGE = 420
```

### 2. Update paginator.py

Modify `../app/paginator.py` to use the compound cost model instead of simple character counting.

## Project Structure

```
budget/
├── server.py              # FastAPI app with routes
├── config.py              # Constants and defaults
├── state.py               # State management
├── content.py             # Content generation
├── calibration.py         # Binary search logic
├── templates/
│   ├── trial.html        # Kindle test page
│   └── status.html       # Desktop dashboard
├── static/
│   └── test_images/      # Test images (user-provided)
├── requirements.txt       # Dependencies
├── calibration_state.json # Generated state (gitignored)
└── README.md             # This file
```

## Troubleshooting

### Port Already in Use
The server automatically tries ports 8080-8090. If all are occupied, it will fail with an error.

### No Content Available
Ensure `../readwise.json` exists and contains articles. The tool needs at least one article with content.

### State Corruption
If `calibration_state.json` becomes corrupted, delete it and restart. The server will create a fresh state.

### Tailscale Connection Issues
- Ensure Tailscale is running and authenticated
- Verify the funnel command uses the correct port from server output
- Check Kindle can access Tailscale network

## Expected Session Duration

- **Phase 1 (Budget)**: 8-12 trials (~5-10 minutes)
- **Phase 2 (Costs)**: 15-25 trials per cost × 5 costs = ~75-125 trials (~30-60 minutes)
- **Phase 3 (Budget Recalibration)**: 5-8 trials (~3-5 minutes)
- **Total**: ~40-60 trials, approximately 50-75 minutes

## Tips for Better Calibration

1. **Keep Kindle font size consistent** - Don't change zoom during calibration
2. **Vary feedback** - Don't just click "just right" on everything
3. **Be honest** - Accurate feedback leads to better calibration
4. **Monitor status** - Check desktop dashboard periodically to see progress
5. **Complete both phases** - Phase 2 fine-tunes the parameters from Phase 1
