import os
from typing import Optional
from dotenv import load_dotenv
from .config_handler import is_slack_enabled

load_dotenv()


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    return val


# Always required
DATABASE_URL: str = _require("DATABASE_URL")
JWT_SECRET: str = _require("JWT_SECRET")

# Conditionally required based on config.json having slack
if is_slack_enabled():
    SLACK_CLIENT_ID: str = _require("SLACK_CLIENT_ID")
    SLACK_CLIENT_SECRET: str = _require("SLACK_CLIENT_SECRET")
    SLACK_REDIRECT_URI: str = _require("SLACK_REDIRECT_URI")

