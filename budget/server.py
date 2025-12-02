#!/usr/bin/env python3
# /// script
# dependencies = [
#   "fastapi>=0.100.0",
#   "uvicorn[standard]>=0.23.0",
#   "jinja2>=3.1.0",
#   "beautifulsoup4>=4.12.0",
#   "python-dotenv>=1.0.0",
# ]
# ///
"""FastAPI server for Kindle calibration."""
import socket
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import state
import calibration
import content
from config import (
    HOST,
    PORT_START,
    PORT_MAX_ATTEMPTS,
    TAILSCALE_FUNNEL_PORT,
    STATIC_DIR,
)

app = FastAPI(title="Kindle Calibration Tool")

# Setup templates and static files
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def show_trial(request: Request):
    """
    Display current trial page for Kindle.

    Generates new trial based on current calibration state.
    """
    # Load state
    current_state = state.load_state()

    # Select next target and what we're testing
    target_size, testing_element = calibration.select_next_target(current_state)

    # Get current costs
    costs = {name: data["current"] for name, data in current_state["costs"].items()}

    # Generate composition
    emphasis = testing_element if current_state["phase"] == "costs" else None
    composition = calibration.generate_target_composition(
        target_size, costs, emphasis=emphasis
    )

    # Render content
    content_html, effective_size = content.render_page(
        composition, costs, trial_id=""  # Will be set after recording
    )

    # Hash content
    content_hash = state.hash_content(content_html)

    # Record trial
    trial_id = state.record_trial(
        current_state,
        composition,
        effective_size,
        content_hash,
        testing_element=testing_element,
    )

    # Prepare template context
    context = {
        "request": request,
        "trial_id": trial_id,
        "phase": current_state["phase"],
        "testing": testing_element or "budget",
        "effective_size": effective_size,
        "composition": composition,
        "content": content_html,
        # Pass individual composition values for metadata display
        "chars": composition["chars"],
        "para": composition["para"],
        "h2": composition["h2"],
        "h3": composition["h3"],
        "blockquote": composition["blockquote"],
        "image": composition["image"],
    }

    return templates.TemplateResponse("trial.html", context)


@app.get("/feedback/{trial_id}/{response}", response_class=RedirectResponse)
async def record_feedback(trial_id: str, response: str):
    """
    Record user feedback and redirect to next trial.

    Args:
        trial_id: UUID of trial
        response: "too_big", "too_small", or "just_right"
    """
    # Validate response
    if response not in ["too_big", "too_small", "just_right"]:
        return JSONResponse({"error": "Invalid feedback"}, status_code=400)

    # Load state
    current_state = state.load_state()

    # Update feedback
    state.update_feedback(current_state, trial_id, response)

    # Update calibration based on feedback
    calibration.update_from_feedback(current_state, trial_id, response)

    # Save updated state
    state.save_state(current_state)

    # Redirect to next trial (absolute path now that we removed /calibrate prefix)
    return RedirectResponse(url="/", status_code=303)


@app.get("/status", response_class=HTMLResponse)
async def show_status(request: Request):
    """
    Display calibration status dashboard (for desktop).

    Shows convergence progress, recent trials, and current parameters.
    """
    current_state = state.load_state()

    # Calculate convergence percentages
    from config import BUDGET_BOUNDS, COST_BOUNDS

    budget_range = current_state["budget"]["high"] - current_state["budget"]["low"]
    initial_budget_range = BUDGET_BOUNDS[1] - BUDGET_BOUNDS[0]
    budget_progress = 100 * (1 - budget_range / initial_budget_range)

    cost_progress = {}
    for name, cost_data in current_state["costs"].items():
        range_size = cost_data["high"] - cost_data["low"]
        initial_range = COST_BOUNDS[name][1] - COST_BOUNDS[name][0]
        progress = 100 * (1 - range_size / initial_range)
        cost_progress[name] = progress

    # Get recent trials
    recent = state.get_recent_trials(current_state, count=20)

    context = {
        "request": request,
        "state": current_state,
        "budget_progress": budget_progress,
        "cost_progress": cost_progress,
        "recent_trials": recent,
    }

    return templates.TemplateResponse("status.html", context)


@app.get("/reset", response_class=RedirectResponse)
async def reset_calibration():
    """Reset calibration state to defaults."""
    state.reset_state()
    return RedirectResponse(url="/status", status_code=303)


@app.get("/export")
async def export_config():
    """
    Export converged values as JSON for manual config update.

    Returns JSON ready to paste into parent app config.
    """
    current_state = state.load_state()

    # Extract converged values
    export_data = {
        "budget": current_state["budget"].get("converged"),
        "costs": {
            name: data.get("converged") or data["current"]
            for name, data in current_state["costs"].items()
        },
        "calibration_complete": current_state["metadata"].get("completed_at")
        is not None,
        "total_trials": current_state["metadata"]["total_trials"],
    }

    return JSONResponse(export_data)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


def find_available_port(start_port: int = PORT_START, max_attempts: int = PORT_MAX_ATTEMPTS) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((HOST, port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"No available ports found in range {start_port}-{start_port + max_attempts}"
    )


if __name__ == "__main__":
    import uvicorn

    port = find_available_port()
    print(f"\n{'=' * 70}")
    print(f"Kindle Calibration Server")
    print(f"{'=' * 70}")
    print(f"Server starting on {HOST}:{port}")
    print(f"Local access: http://localhost:{port}")
    print(f"\nTailscale funnel command (run in another terminal):")
    print(f"  tailscale funnel --https {TAILSCALE_FUNNEL_PORT} {port}")
    print(f"\nThen access on Kindle:")
    print(f"  https://your-machine.ts.net:{TAILSCALE_FUNNEL_PORT}/")
    print(f"{'=' * 70}\n")

    uvicorn.run(app, host=HOST, port=port)
