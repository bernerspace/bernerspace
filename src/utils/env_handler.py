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


def _optional(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None else default


# Always required
DATABASE_URL: str = _require("DATABASE_URL")

# Auth configuration (either JWT_SECRET for HS256 or JWT_JWKS_URL for RS256 JWKS)
# Make both optional; middleware will decide which to use. By request, set a default JWKS URL.
JWT_SECRET: Optional[str] = _optional("JWT_SECRET")
JWT_JWKS_URL: Optional[str] = _optional("JWT_JWKS_URL")
# Optional issuer/audience validation
JWT_ISSUER: Optional[str] = _optional("JWT_ISSUER")
JWT_AUDIENCE: Optional[str] = _optional("JWT_AUDIENCE")

# Optional header-based auth passthrough
AUTH_ALLOW_USER_ID_HEADER: str = _optional("AUTH_ALLOW_USER_ID_HEADER", "false") or "false"
AUTH_USER_ID_HEADER_NAME: str = _optional("AUTH_USER_ID_HEADER_NAME", "x-user-id") or "x-user-id"

# Conditionally required based on config.json having slack
if is_slack_enabled():
    SLACK_CLIENT_ID: str = _require("SLACK_CLIENT_ID")
    SLACK_CLIENT_SECRET: str = _require("SLACK_CLIENT_SECRET")
    SLACK_REDIRECT_URI: str = _require("SLACK_REDIRECT_URI")

# Encryption keys for token column (comma-separated MultiFernet keys)
TOKEN_ENCRYPTION_KEYS_RAW: Optional[str] = _optional("TOKEN_ENCRYPTION_KEYS")
TOKEN_ENCRYPTION_KEYS = [k.strip() for k in TOKEN_ENCRYPTION_KEYS_RAW.split(",")] if TOKEN_ENCRYPTION_KEYS_RAW else []

