"""Configuration for Kindle calibration tool."""
from pathlib import Path
from typing import Dict, Tuple

# Paths
BUDGET_DIR = Path(__file__).parent
PARENT_DIR = BUDGET_DIR.parent
READWISE_JSON_PATH = PARENT_DIR / "readwise.json"
STATE_FILE_PATH = BUDGET_DIR / "calibration_state.json"
STATIC_DIR = BUDGET_DIR / "static"
TEST_IMAGES_DIR = STATIC_DIR / "test_images"

# Default cost multipliers (in character equivalents)
DEFAULT_COSTS: Dict[str, int] = {
    "para": 60,       # Paragraph margin overhead
    "h2": 140,        # H2 header with larger font + margins
    "h3": 100,        # H3 header
    "blockquote": 80, # Blockquote with indentation
    "image": 400,     # Image placeholder cost (varies by size)
}

# Cost bounds for binary search (min, max)
COST_BOUNDS: Dict[str, Tuple[int, int]] = {
    "para": (20, 150),
    "h2": (60, 250),
    "h3": (40, 180),
    "blockquote": (30, 150),
    "image": (150, 800),
}

# Budget bounds (min, max)
BUDGET_BOUNDS: Tuple[int, int] = (800, 3500)
DEFAULT_BUDGET: int = 2000

# Convergence settings
CONVERGENCE_THRESHOLD: int = 50  # Stop when range < this
MIN_TRIALS_PER_PHASE: int = 5    # Minimum trials before phase switch
MIN_TRIALS_PER_COST: int = 3     # Min trials per cost element

# Content generation parameters
MIN_CHARS_FOR_CONTENT: int = 200  # Minimum text content
MAX_PARAS_PER_PAGE: int = 15      # Maximum paragraphs to generate
MAX_HEADERS_PER_PAGE: int = 5     # Maximum headers
MAX_IMAGES_PER_PAGE: int = 3      # Maximum images
MAX_BLOCKQUOTES_PER_PAGE: int = 3 # Maximum blockquotes

# Composition emphasis profiles for cost calibration
# Higher weight = more of that element when calibrating
EMPHASIS_PROFILES: Dict[str, Dict[str, float]] = {
    "para": {
        "para_weight": 3.0,
        "h2_weight": 0.5,
        "h3_weight": 0.5,
        "blockquote_weight": 0.3,
        "image_weight": 0.2,
    },
    "h2": {
        "para_weight": 1.0,
        "h2_weight": 3.0,
        "h3_weight": 0.5,
        "blockquote_weight": 0.3,
        "image_weight": 0.2,
    },
    "h3": {
        "para_weight": 1.0,
        "h2_weight": 0.3,
        "h3_weight": 3.0,
        "blockquote_weight": 0.3,
        "image_weight": 0.2,
    },
    "blockquote": {
        "para_weight": 1.0,
        "h2_weight": 0.3,
        "h3_weight": 0.3,
        "blockquote_weight": 3.0,
        "image_weight": 0.2,
    },
    "image": {
        "para_weight": 1.0,
        "h2_weight": 0.3,
        "h3_weight": 0.3,
        "blockquote_weight": 0.2,
        "image_weight": 3.0,
    },
}

# Server settings
HOST: str = "0.0.0.0"
PORT_START: int = 8080
PORT_MAX_ATTEMPTS: int = 10
TAILSCALE_FUNNEL_PORT: int = 10000  # For user reference


def validate_config() -> None:
    """Validate required configuration."""
    if not READWISE_JSON_PATH.exists():
        raise FileNotFoundError(
            f"readwise.json not found at {READWISE_JSON_PATH}. "
            f"Please ensure the parent directory contains readwise.json"
        )

    # Create directories if they don't exist
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    TEST_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def get_test_images() -> list[str]:
    """Get list of available test image filenames."""
    if not TEST_IMAGES_DIR.exists():
        return []

    images = list(TEST_IMAGES_DIR.glob("*.jpg")) + list(TEST_IMAGES_DIR.glob("*.png"))
    return [img.name for img in images]


# Validate on import
validate_config()
