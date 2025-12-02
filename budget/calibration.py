"""Calibration logic for binary search and cost adjustment."""
import random
from datetime import datetime
from typing import Dict, Tuple, Optional, Any

from config import (
    CONVERGENCE_THRESHOLD,
    MIN_TRIALS_PER_PHASE,
    MIN_TRIALS_PER_COST,
    DEFAULT_COSTS,
    EMPHASIS_PROFILES,
    MAX_PARAS_PER_PAGE,
    MAX_HEADERS_PER_PAGE,
    MAX_IMAGES_PER_PAGE,
    MAX_BLOCKQUOTES_PER_PAGE,
    BUDGET_BOUNDS,
)


def calculate_effective_size(composition: Dict[str, int], costs: Dict[str, int]) -> int:
    """
    Calculate effective size using compound cost model.

    effective_size = chars + (para_count * PARA_COST) + ...
    """
    effective = composition.get("chars", 0)

    for element in ["para", "h2", "h3", "blockquote", "image"]:
        count = composition.get(element, 0)
        cost = costs.get(element, DEFAULT_COSTS.get(element, 0))
        effective += count * cost

    return effective


def check_budget_convergence(state: Dict[str, Any]) -> bool:
    """Check if budget has converged."""
    budget = state["budget"]

    # Check range threshold
    range_size = budget["high"] - budget["low"]
    if range_size < CONVERGENCE_THRESHOLD:
        return True

    # Check if we have "just_right" feedback or converged value
    if budget["converged"] is not None:
        return True

    return False


def check_cost_convergence(state: Dict[str, Any], cost_name: str) -> bool:
    """Check if specific cost has converged."""
    cost = state["costs"][cost_name]

    # Already locked
    if cost["locked"]:
        return True

    # Check range threshold
    range_size = cost["high"] - cost["low"]
    if range_size < CONVERGENCE_THRESHOLD:
        return True

    # Check if converged value set
    if cost["converged"] is not None:
        return True

    return False


def check_all_costs_converged(state: Dict[str, Any]) -> bool:
    """Check if all costs have converged."""
    return all(
        check_cost_convergence(state, cost_name) for cost_name in state["costs"].keys()
    )


def select_next_target(state: Dict[str, Any]) -> Tuple[int, Optional[str]]:
    """
    Select next target effective size and what's being tested.
    Returns: (target_size, testing_element)
    """
    if state["phase"] == "budget":
        # Use current budget value
        target = state["budget"]["current"]
        return (target, None)

    elif state["phase"] == "costs":
        # Find first unlocked cost with widest range
        unlocked = {
            name: cost
            for name, cost in state["costs"].items()
            if not cost["locked"]
        }

        if not unlocked:
            # All locked, we're done
            return (state["budget"]["converged"], None)

        # Pick cost with widest range
        widest_name = max(
            unlocked.keys(), key=lambda n: unlocked[n]["high"] - unlocked[n]["low"]
        )

        # Use converged budget as target
        target = state["budget"]["converged"]
        return (target, widest_name)

    elif state["phase"] == "budget_recal":
        # Re-calibrating budget with locked costs
        target = state["budget"]["current"]
        return (target, None)

    else:
        raise ValueError(f"Unknown phase: {state['phase']}")


def generate_target_composition(
    target_size: int, costs: Dict[str, int], emphasis: Optional[str] = None
) -> Dict[str, int]:
    """
    Generate composition that approximates target_size.

    This is an inverse problem: given target and costs, find plausible
    composition. Uses randomization within reasonable bounds.

    If emphasis is set, bias toward that element type.
    """
    composition = {"chars": 0, "para": 0, "h2": 0, "h3": 0, "blockquote": 0, "image": 0}

    # Get emphasis weights
    if emphasis and emphasis in EMPHASIS_PROFILES:
        weights = EMPHASIS_PROFILES[emphasis]
    else:
        # Balanced composition
        weights = {
            "para_weight": 1.0,
            "h2_weight": 0.5,
            "h3_weight": 0.5,
            "blockquote_weight": 0.3,
            "image_weight": 0.3,
        }

    # Start with character budget (50-70% of target)
    char_budget_ratio = random.uniform(0.5, 0.7)
    remaining = target_size
    composition["chars"] = int(target_size * char_budget_ratio)
    remaining -= composition["chars"]

    # Allocate remaining budget to elements based on weights
    # Generate paragraphs (always need at least 1)
    avg_para_cost = costs.get("para", DEFAULT_COSTS["para"])
    max_paras = min(
        int(remaining * weights["para_weight"] / avg_para_cost), MAX_PARAS_PER_PAGE
    )
    composition["para"] = random.randint(max(1, max_paras // 2), max(1, max_paras))
    remaining -= composition["para"] * costs.get("para", DEFAULT_COSTS["para"])

    # Generate H2 headers
    if remaining > costs.get("h2", DEFAULT_COSTS["h2"]):
        max_h2 = min(
            int(remaining * weights["h2_weight"] / costs.get("h2", DEFAULT_COSTS["h2"])),
            MAX_HEADERS_PER_PAGE,
        )
        composition["h2"] = random.randint(0, max(0, max_h2))
        remaining -= composition["h2"] * costs.get("h2", DEFAULT_COSTS["h2"])

    # Generate H3 headers
    if remaining > costs.get("h3", DEFAULT_COSTS["h3"]):
        max_h3 = min(
            int(remaining * weights["h3_weight"] / costs.get("h3", DEFAULT_COSTS["h3"])),
            MAX_HEADERS_PER_PAGE,
        )
        composition["h3"] = random.randint(0, max(0, max_h3))
        remaining -= composition["h3"] * costs.get("h3", DEFAULT_COSTS["h3"])

    # Generate blockquotes
    if remaining > costs.get("blockquote", DEFAULT_COSTS["blockquote"]):
        max_bq = min(
            int(
                remaining
                * weights["blockquote_weight"]
                / costs.get("blockquote", DEFAULT_COSTS["blockquote"])
            ),
            MAX_BLOCKQUOTES_PER_PAGE,
        )
        composition["blockquote"] = random.randint(0, max(0, max_bq))
        remaining -= composition["blockquote"] * costs.get(
            "blockquote", DEFAULT_COSTS["blockquote"]
        )

    # Generate images
    if remaining > costs.get("image", DEFAULT_COSTS["image"]):
        max_img = min(
            int(
                remaining
                * weights["image_weight"]
                / costs.get("image", DEFAULT_COSTS["image"])
            ),
            MAX_IMAGES_PER_PAGE,
        )
        composition["image"] = random.randint(0, max(0, max_img))
        remaining -= composition["image"] * costs.get("image", DEFAULT_COSTS["image"])

    return composition


def update_from_feedback(state: Dict[str, Any], trial_id: str, feedback: str) -> None:
    """
    Update state based on feedback using binary search logic.
    """
    trial = next((t for t in state["trials"] if t["id"] == trial_id), None)
    if not trial:
        raise ValueError(f"Trial {trial_id} not found")

    if state["phase"] == "budget":
        _update_budget_from_feedback(state, feedback)
    elif state["phase"] == "costs":
        _update_cost_from_feedback(state, trial, feedback)
    elif state["phase"] == "budget_recal":
        _update_budget_recal_from_feedback(state, feedback)


def _initiate_budget_recalibration(state: Dict[str, Any]) -> None:
    """
    Initiate Phase 3: Budget recalibration with locked costs.

    After costs are calibrated, the budget from Phase 1 is likely invalid
    because it was calibrated with default costs. Re-run budget calibration
    with the new locked cost values.
    """
    budget = state["budget"]

    # Reset budget bounds to a reasonable range around current converged value
    # Use a range of ±30% of current value
    current_budget = budget["converged"]
    margin = int(current_budget * 0.3)

    budget["low"] = max(BUDGET_BOUNDS[0], current_budget - margin)
    budget["high"] = min(BUDGET_BOUNDS[1], current_budget + margin)
    budget["current"] = (budget["low"] + budget["high"]) // 2
    budget["converged"] = None  # Unlock for recalibration
    budget["history"].append(budget["current"])

    # Transition to budget_recal phase
    state["phase"] = "budget_recal"


def _update_budget_recal_from_feedback(state: Dict[str, Any], feedback: str) -> None:
    """
    Update budget bounds during recalibration phase.
    Similar to initial budget calibration but marks complete instead of transitioning.
    """
    budget = state["budget"]
    current = budget["current"]

    if feedback == "just_right":
        # Lock this value
        budget["converged"] = current

        # Mark calibration as complete
        if state["metadata"]["budget_recal_trials"] >= MIN_TRIALS_PER_PHASE:
            if check_budget_convergence(state):
                state["metadata"]["completed_at"] = datetime.utcnow().isoformat() + "Z"

    elif feedback == "too_big":
        # Page was too big, reduce upper bound
        budget["high"] = current
        new_current = (budget["low"] + budget["high"]) // 2
        budget["current"] = new_current
        budget["history"].append(new_current)

        # Auto-converge if range is small
        if budget["high"] - budget["low"] < CONVERGENCE_THRESHOLD:
            budget["converged"] = new_current
            if state["metadata"]["budget_recal_trials"] >= MIN_TRIALS_PER_PHASE:
                state["metadata"]["completed_at"] = datetime.utcnow().isoformat() + "Z"

    elif feedback == "too_small":
        # Page was too small, increase lower bound
        budget["low"] = current
        new_current = (budget["low"] + budget["high"]) // 2
        budget["current"] = new_current
        budget["history"].append(new_current)

        # Auto-converge if range is small
        if budget["high"] - budget["low"] < CONVERGENCE_THRESHOLD:
            budget["converged"] = new_current
            if state["metadata"]["budget_recal_trials"] >= MIN_TRIALS_PER_PHASE:
                state["metadata"]["completed_at"] = datetime.utcnow().isoformat() + "Z"


def _update_budget_from_feedback(state: Dict[str, Any], feedback: str) -> None:
    """Update budget bounds based on feedback."""
    budget = state["budget"]
    current = budget["current"]

    if feedback == "just_right":
        # Lock this value
        budget["converged"] = current

        # Check for phase transition
        if state["metadata"]["budget_trials"] >= MIN_TRIALS_PER_PHASE:
            if check_budget_convergence(state):
                state["phase"] = "costs"

    elif feedback == "too_big":
        # Page was too big, reduce upper bound
        budget["high"] = current
        new_current = (budget["low"] + budget["high"]) // 2
        budget["current"] = new_current
        budget["history"].append(new_current)

        # Auto-converge if range is small
        if budget["high"] - budget["low"] < CONVERGENCE_THRESHOLD:
            budget["converged"] = new_current
            if state["metadata"]["budget_trials"] >= MIN_TRIALS_PER_PHASE:
                state["phase"] = "costs"

    elif feedback == "too_small":
        # Page was too small, increase lower bound
        budget["low"] = current
        new_current = (budget["low"] + budget["high"]) // 2
        budget["current"] = new_current
        budget["history"].append(new_current)

        # Auto-converge if range is small
        if budget["high"] - budget["low"] < CONVERGENCE_THRESHOLD:
            budget["converged"] = new_current
            if state["metadata"]["budget_trials"] >= MIN_TRIALS_PER_PHASE:
                state["phase"] = "costs"


def _update_cost_from_feedback(
    state: Dict[str, Any], trial: Dict[str, Any], feedback: str
) -> None:
    """
    Update cost multiplier based on feedback.

    Strategy: If page with emphasis on element X systematically overflows,
    the cost for X is too low (increase it). If systematically underflows,
    cost is too high (decrease it).
    """
    testing_element = trial.get("testing_element")
    if not testing_element:
        return  # Can't adjust without knowing what we're testing

    cost = state["costs"][testing_element]
    current = cost["current"]

    if feedback == "just_right":
        # This cost value is good
        cost["converged"] = current
        cost["locked"] = True

    elif feedback == "too_big":
        # Page overflowed despite being under budget
        # This means cost is underestimated - increase it
        cost["low"] = current
        new_current = (cost["low"] + cost["high"]) // 2
        cost["current"] = new_current
        cost["history"].append(new_current)

        # Auto-lock if range is small
        if cost["high"] - cost["low"] < CONVERGENCE_THRESHOLD:
            cost["converged"] = new_current
            cost["locked"] = True

    elif feedback == "too_small":
        # Page underflowed despite approaching budget
        # Cost might be overestimated - decrease it
        cost["high"] = current
        new_current = (cost["low"] + cost["high"]) // 2
        cost["current"] = new_current
        cost["history"].append(new_current)

        # Auto-lock if range is small
        if cost["high"] - cost["low"] < CONVERGENCE_THRESHOLD:
            cost["converged"] = new_current
            cost["locked"] = True

    # Check if all costs converged - transition to budget recalibration
    if check_all_costs_converged(state):
        # Don't mark as completed yet - need to recalibrate budget
        # Transition to budget_recal phase
        _initiate_budget_recalibration(state)
