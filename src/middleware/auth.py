from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp import Context
from typing import  Optional, Dict, Any
import jwt as pyjwt

# JWT Auth Middleware
class JWTAuthMiddleware(Middleware):
    def __init__(self, secret_key: str, issuer: str, audience: str):
        self.secret_key = secret_key
        self.issuer = issuer
        self.audience = audience
    
    def extract_token_from_context(self, context: MiddlewareContext) -> Optional[str]:
        try:
            headers = get_http_headers(include_all=True)
            auth_header = headers.get("authorization")
            if auth_header and auth_header.lower().startswith("bearer "):
                token = auth_header.split(" ")[1]
                return token
        except Exception:
            pass
        return None
    
    def verify_token(self, token: str) -> Optional[Dict]:
        try:
            payload = pyjwt.decode(
                token,
                self.secret_key,
                algorithms=["HS256"],
                issuer=self.issuer,
                audience=self.audience
            )
            return payload
        except pyjwt.ExpiredSignatureError:
            return None
        except pyjwt.InvalidTokenError:
            return None
    
    async def on_message(self, context: MiddlewareContext, call_next):
        token = self.extract_token_from_context(context)
        payload = None
        if token:
            payload = self.verify_token(token)
            if payload:
                user_id = payload.get('sub')
                if context.fastmcp_context:
                    context.fastmcp_context.set_state("user_id", user_id)
                    context.fastmcp_context.set_state("jwt_payload", payload)
        try:
            result = await call_next(context)
            return result
        except Exception as e:
            raise

def extract_user_from_context(ctx: Context) -> str:
    jwt_payload = ctx.get_state("jwt_payload")
    return jwt_payload.get('sub') if jwt_payload else None

