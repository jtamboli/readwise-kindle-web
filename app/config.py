"""Configuration management for Readwise Kindle Web Reader."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # Readwise API token (required)
    READWISE_API_TOKEN = os.getenv("READWISE_API_TOKEN")

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
