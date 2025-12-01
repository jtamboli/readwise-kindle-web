"""Configuration management for Readwise Kindle Web Reader."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # Readwise API token (required)
    READWISE_API_TOKEN = os.getenv("READWISE_API_TOKEN")

    # Pagination settings
    KINDLE_PAGE_CHAR_BUDGET = int(os.getenv("KINDLE_PAGE_CHAR_BUDGET", "1800"))
    IMAGE_SEPARATE_PAGE = os.getenv("IMAGE_SEPARATE_PAGE", "true").lower() == "true"

    # Cache settings
    CACHE_LIST_TTL = int(os.getenv("CACHE_LIST_TTL", "300"))  # 5 minutes

    # Readwise API endpoint
    READWISE_API_BASE = "https://readwise.io/api/v3"

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.READWISE_API_TOKEN:
            raise ValueError("READWISE_API_TOKEN environment variable is required")


# Validate configuration on import
Config.validate()
