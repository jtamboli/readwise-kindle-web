"""Configuration management for Readwise Kindle Web Reader."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # Readwise API token (required)
    KINDLE_READWISE_API_TOKEN = os.getenv("KINDLE_READWISE_API_TOKEN")

    # Cache settings
    KINDLE_CACHE_LIST_TTL = int(os.getenv("KINDLE_CACHE_LIST_TTL", "300"))  # 5 minutes

    # HTTP Basic Auth (optional). When both are set, every request requires
    # these credentials. Leave unset to disable auth (e.g. local network use).
    BASIC_AUTH_USERNAME = os.getenv("BASIC_AUTH_USERNAME")
    BASIC_AUTH_PASSWORD = os.getenv("BASIC_AUTH_PASSWORD")

    @classmethod
    def basic_auth_enabled(cls):
        """Auth is active only when both username and password are configured."""
        return bool(cls.BASIC_AUTH_USERNAME and cls.BASIC_AUTH_PASSWORD)

    # Logging settings
    KINDLE_READWISE_VERBOSE = os.getenv("KINDLE_READWISE_VERBOSE", "false").lower() == "true"

    # Readwise API endpoint
    READWISE_API_BASE = "https://readwise.io/api/v3"

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.KINDLE_READWISE_API_TOKEN:
            raise ValueError("KINDLE_READWISE_API_TOKEN environment variable is required")


# Validate configuration on import
Config.validate()
