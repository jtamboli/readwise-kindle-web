"""Configuration management for Readwise Kindle Web Reader."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # Readwise API token (required)
    READWISE_API_TOKEN = os.getenv("READWISE_API_TOKEN")

    # ============================================================================
    # KINDLE PAGE LAYOUT - CALIBRATED VALUES
    # ============================================================================
    # These values were empirically determined using the budget calibration tool
    # Calibrated: 2025-12-02
    # Device: Kindle Paperwhite
    # Total calibration trials: 24
    # Notes: Originally calibrated with 16px font
    # Adjusted: 2025-12-04 for 18px font size (1.125x ratio, metrics divided by 1.125)

    # Maximum effective size for a single page
    # This is the target threshold - pages should not exceed this value
    KINDLE_PAGE_BUDGET = 1403  # Adjusted from 1578 for 18px font

    # Cost multipliers for different HTML elements
    # These represent the vertical space overhead beyond raw character count
    KINDLE_COST_PARA = 93       # Adjusted from 105 for 18px font
    KINDLE_COST_H2 = 136        # Adjusted from 153 for 18px font
    KINDLE_COST_H3 = 89         # Adjusted from 100 for 18px font
    KINDLE_COST_BLOCKQUOTE = 49 # Adjusted from 55 for 18px font
    KINDLE_COST_IMAGE = 244     # Adjusted from 275 for 18px font

    # Compound cost formula:
    # effective_size = chars + (para_count × PARA_COST) + (h2_count × H2_COST) +
    #                  (h3_count × H3_COST) + (blockquote_count × BQ_COST) +
    #                  (image_count × IMAGE_COST)

    # Legacy pagination setting (deprecated - use KINDLE_PAGE_BUDGET instead)
    KINDLE_PAGE_CHAR_BUDGET = int(os.getenv("KINDLE_PAGE_CHAR_BUDGET", "1800"))
    IMAGE_SEPARATE_PAGE = os.getenv("IMAGE_SEPARATE_PAGE", "true").lower() == "true"

    # Cache settings
    CACHE_LIST_TTL = int(os.getenv("CACHE_LIST_TTL", "300"))  # 5 minutes

    # Logging settings
    KINDLE_READWISE_VERBOSE = os.getenv("KINDLE_READWISE_VERBOSE", "false").lower() == "true"

    # Readwise API endpoint
    READWISE_API_BASE = "https://readwise.io/api/v3"

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.READWISE_API_TOKEN:
            raise ValueError("READWISE_API_TOKEN environment variable is required")


# Validate configuration on import
Config.validate()
