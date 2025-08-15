from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp import Context
from typing import Optional, Dict, Any
import time
import httpx
import jwt as pyjwt
from jwt import algorithms
from src.utils.env_handler import (
    JWT_JWKS_URL as ENV_JWKS_URL,
    AUTH_ALLOW_USER_ID_HEADER as ENV_AUTH_ALLOW_USER_ID_HEADER,
    AUTH_USER_ID_HEADER_NAME as ENV_AUTH_USER_ID_HEADER_NAME,
)
import logging
import json

logger = logging.getLogger(__name__)

# JWT Auth Middleware
class JWTAuthMiddleware(Middleware):
    def __init__(
        self,
        secret_key: Optional[str] = None,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        jwks_url: Optional[str] = None,
        allow_user_id_header: Optional[bool] = None,
        user_id_header_name: Optional[str] = None,
        jwks_ttl_seconds: int = 3600,
    ):
        # Backward compatible ctor: accept HS256 secret or a JWKS URL via secret_key
        self.secret_key = secret_key
        self.issuer = issuer
        self.audience = audience

        # Config can come from args or env handler
        self.jwks_url = (
            jwks_url
            or (secret_key if (isinstance(secret_key, str) and secret_key.startswith("http")) else None)
            or ENV_JWKS_URL
        )
        # Feature flag: allow user id via header
        env_allow = str(ENV_AUTH_ALLOW_USER_ID_HEADER or "false").lower() in {"1", "true", "yes"}
        self.allow_user_id_header = allow_user_id_header if allow_user_id_header is not None else env_allow
        self.user_id_header_name = (
            user_id_header_name or ENV_AUTH_USER_ID_HEADER_NAME or "x-user-id"
        ).lower()

        # JWKS cache
        self._jwks_cache: Dict[str, Any] = {}
        self._jwks_last_fetch: float = 0.0
        self._jwks_ttl_seconds = jwks_ttl_seconds

        logger.debug("JWTAuthMiddleware configured: jwks_url=%s, allow_user_id_header=%s, user_id_header_name=%s",
                     self.jwks_url, self.allow_user_id_header, self.user_id_header_name)

    def extract_token_from_context(self, context: MiddlewareContext) -> Optional[str]:
        try:
            headers = get_http_headers(include_all=True)
            logger.debug("Extracting token from headers: %s", headers)
            auth_header = headers.get("authorization")
            if auth_header and auth_header.lower().startswith("bearer "):
                token = auth_header.split(" ", 1)[1]
                return token
        except Exception as e:
            logger.exception("Failed to extract token from context: %s", e)
        return None

    async def _fetch_jwks(self) -> Dict[str, Any]:
        if not self.jwks_url:
            logger.debug("No JWKS URL configured, skipping fetch.")
            return {"keys": []}
        now = time.time()
        # If cache exists and is fresh, return it
        if self._jwks_cache and (now - self._jwks_last_fetch) < self._jwks_ttl_seconds:
            logger.debug("Using cached JWKS (age=%.1fs)", now - self._jwks_last_fetch)
            return self._jwks_cache
        try:
            logger.debug("Fetching JWKS from %s", self.jwks_url)
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(self.jwks_url)
                resp.raise_for_status()
                data = resp.json()
                # Normalize to dict with 'keys'
                if isinstance(data, dict) and "keys" in data:
                    self._jwks_cache = data
                else:
                    self._jwks_cache = {"keys": data if isinstance(data, list) else []}
                self._jwks_last_fetch = now
                logger.debug("JWKS fetched: %d keys", len(self._jwks_cache.get("keys", [])))
        except Exception as e:
            # Leave cache as-is on failure but log the error
            logger.exception("Failed to fetch JWKS from %s: %s", self.jwks_url, e)
            if not self._jwks_cache:
                # Ensure we return a consistent structure
                self._jwks_cache = {"keys": []}
        return self._jwks_cache

    async def _get_public_key_from_jwks(self, token: str) -> Optional[Any]:
        try:
            header = pyjwt.get_unverified_header(token)
            kid = header.get("kid")
            alg = header.get("alg")
            if not kid:
                logger.warning("Token header has no 'kid'")
                return None
            jwks = await self._fetch_jwks()
            for jwk in jwks.get("keys", []):
                if jwk.get("kid") == kid:
                    # Prepare JWK JSON string
                    try:
                        jwk_json = json.dumps(jwk)
                    except Exception:
                        jwk_json = None
                    kty = jwk.get("kty")
                    try:
                        if kty == "RSA":
                            # RSA public key
                            if jwk_json:
                                return algorithms.RSAAlgorithm.from_jwk(jwk_json)
                            else:
                                # fallback: try passing dict (some versions accept it)
                                return algorithms.RSAAlgorithm.from_jwk(jwk)
                        elif kty == "EC":
                            if jwk_json:
                                return algorithms.ECAlgorithm.from_jwk(jwk_json)
                            else:
                                return algorithms.ECAlgorithm.from_jwk(jwk)
                        else:
                            # Try generic from_jwk with JSON string when possible
                            if jwk_json:
                                return algorithms.RSAAlgorithm.from_jwk(jwk_json)
                    except Exception as e:
                        logger.exception("Failed to construct public key from JWK (kid=%s, kty=%s): %s", kid, kty, e)
                        # continue trying other keys (unlikely)
            logger.warning("No matching JWK found for kid=%s", kid)
        except Exception as e:
            logger.exception("Error while extracting public key from JWKS: %s", e)
            return None
        return None

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            # Try JWKS-based verification first (RS* family)
            if self.jwks_url:
                # Try to obtain public key for this token
                public_key = await self._get_public_key_from_jwks(token)
                if not public_key:
                    logger.warning("Public key not found via JWKS for token")
                    return None
                # Prefer to use algorithm from token header
                try:
                    header = pyjwt.get_unverified_header(token)
                    alg = header.get("alg")
                except Exception:
                    alg = None
                algorithms_list = [alg] if alg else ["RS256"]

                decode_kwargs = {}
                if self.issuer:
                    decode_kwargs["issuer"] = self.issuer
                if self.audience:
                    decode_kwargs["audience"] = self.audience

                return pyjwt.decode(
                    token,
                    key=public_key,
                    algorithms=algorithms_list,
                    **decode_kwargs,
                )
            elif self.secret_key:
                # HS256 fallback
                decode_kwargs = {}
                if self.issuer:
                    decode_kwargs["issuer"] = self.issuer
                if self.audience:
                    decode_kwargs["audience"] = self.audience
                return pyjwt.decode(
                    token,
                    key=self.secret_key,
                    algorithms=["HS256"],
                    **decode_kwargs,
                )
            else:
                logger.warning("No JWKS URL or secret key configured for JWT verification")
                return None
        except pyjwt.ExpiredSignatureError:
            logger.info("Token expired")
            return None
        except pyjwt.InvalidTokenError as e:
            logger.warning("Invalid token: %s", e)
            return None
        except Exception as e:
            logger.exception("Unexpected error while verifying token: %s", e)
            return None

    async def on_message(self, context: MiddlewareContext, call_next):
        # 1) Optional user-id passthrough from header
        try:
            if self.allow_user_id_header:
                headers = get_http_headers(include_all=True)
                user_id = headers.get(self.user_id_header_name)
                print(f"Extracted user_id from header: {user_id}")
                if user_id and context.fastmcp_context:
                    logger.debug("Using user-id from header: %s", user_id)
                    context.fastmcp_context.set_state("user_id", user_id)
                    context.fastmcp_context.set_state("jwt_payload", {"sub": user_id, "auth": "header"})
                    return await call_next(context)
        except Exception:
            # Ignore and continue with JWT flow
            logger.exception("Error when attempting user-id passthrough from header")

        # 2) JWT flow (HS256 or JWKS/RS256)
        token = self.extract_token_from_context(context)
        payload = None
        if token:
            payload = await self.verify_token(token)
            if payload and context.fastmcp_context:
                user_id = payload.get("sub")
                print(f"Extracted user_id from JWT: {user_id}")
                logger.debug("Authenticated user from JWT: %s", user_id)
                context.fastmcp_context.set_state("user_id", user_id)
                context.fastmcp_context.set_state("jwt_payload", payload)
        else:
            logger.debug("No token found in request")
        try:
            result = await call_next(context)
            return result
        except Exception as e:
            logger.exception("Error in call_next: %s", e)
            raise


def extract_user_from_context(ctx: Context) -> Optional[str]:
    jwt_payload = ctx.get_state("jwt_payload")
    return jwt_payload.get("sub") if jwt_payload else None

