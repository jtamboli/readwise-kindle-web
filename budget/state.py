"""State management for calibration data."""
import json
import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any

from config import (
    STATE_FILE_PATH,
    DEFAULT_COSTS,
    COST_BOUNDS,
    BUDGET_BOUNDS,
    DEFAULT_BUDGET,
)


def create_initial_state() -> Dict[str, Any]:
    """Create fresh state with defaults."""
    return {
        "version": 1,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "phase": "budget",
        "budget": {
            "low": BUDGET_BOUNDS[0],
            "high": BUDGET_BOUNDS[1],
            "current": DEFAULT_BUDGET,
            "converged": None,
            "history": [DEFAULT_BUDGET],
        },
        "costs": {
            name: {
                "low": COST_BOUNDS[name][0],
                "high": COST_BOUNDS[name][1],
                "current": DEFAULT_COSTS[name],
                "locked": False,
                "converged": None,
                "history": [DEFAULT_COSTS[name]],
            }
            for name in DEFAULT_COSTS.keys()
        },
        "trials": [],
        "metadata": {
            "total_trials": 0,
            "budget_trials": 0,
            "cost_trials": 0,
            "budget_recal_trials": 0,
            "completed_at": None,
        },
    }


def load_state() -> Dict[str, Any]:
    """Load state from file or create new."""
    if STATE_FILE_PATH.exists():
        try:
            with open(STATE_FILE_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load state file: {e}")
            print("Creating fresh state...")
            return create_initial_state()
    return create_initial_state()


def save_state(state: Dict[str, Any]) -> None:
    """Save state to file."""
    with open(STATE_FILE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def record_trial(
    state: Dict[str, Any],
    composition: Dict[str, int],
    effective_size: int,
    content_hash: str,
    testing_element: Optional[str] = None,
) -> str:
    """
    Record a new trial without feedback.
    Returns trial_id.
    """
    trial_id = str(uuid.uuid4())
    trial = {
        "id": trial_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "phase": state["phase"],
        "content_hash": content_hash,
        "budget_used": state["budget"]["current"],
        "costs_used": {k: v["current"] for k, v in state["costs"].items()},
        "effective_size": effective_size,
        "composition": composition,
        "feedback": None,
        "testing_element": testing_element,
    }

    state["trials"].append(trial)
    state["metadata"]["total_trials"] += 1

    save_state(state)
    return trial_id


def update_feedback(state: Dict[str, Any], trial_id: str, feedback: str) -> None:
    """Update trial with user feedback."""
    for trial in state["trials"]:
        if trial["id"] == trial_id:
            trial["feedback"] = feedback

            # Increment phase-specific counter
            if trial["phase"] == "budget":
                state["metadata"]["budget_trials"] += 1
            elif trial["phase"] == "budget_recal":
                state["metadata"]["budget_recal_trials"] += 1
            else:
                state["metadata"]["cost_trials"] += 1

            save_state(state)
            return

    raise ValueError(f"Trial {trial_id} not found")


def get_trial(state: Dict[str, Any], trial_id: str) -> Optional[Dict]:
    """Get trial by ID."""
    for trial in state["trials"]:
        if trial["id"] == trial_id:
            return trial
    return None


def get_recent_trials(state: Dict[str, Any], count: int = 10) -> List[Dict]:
    """Get most recent trials."""
    return state["trials"][-count:]


def hash_content(content: str) -> str:
    """Generate SHA256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def reset_state() -> Dict[str, Any]:
    """Reset to initial state."""
    state = create_initial_state()
    save_state(state)
    return state
