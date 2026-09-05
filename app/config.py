"""Configuration management for Readwise Kindle Web Reader."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # Readwise API token (required)
    KINDLE_READWISE_API_TOKEN = os.getenv("KINDLE_READWISE_API_TOKEN")

    # Session token from the official Reader iOS app (optional). The public
    # API cannot write reading position, so when this is set the reader pushes
    # position through the private state-sync API the apps use. Capture the
    # `mobilesession` request header from the app's traffic; see
    # docs/readwise-private-state-api.md. Leave unset to keep position local.
    KINDLE_READWISE_MOBILE_SESSION = os.getenv("KINDLE_READWISE_MOBILE_SESSION")

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

    # Readwise API endpoints
    READWISE_API_BASE = "https://readwise.io/api/v3"
    READWISE_STATE_API_BASE = "https://readwise.io/reader/api"

    @classmethod
    def position_sync_enabled(cls):
        """Reading position is pushed to Readwise only when a session is set."""
        return bool(cls.KINDLE_READWISE_MOBILE_SESSION)

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.KINDLE_READWISE_API_TOKEN:
            raise ValueError("KINDLE_READWISE_API_TOKEN environment variable is required")


# Validate configuration on import
Config.validate()
