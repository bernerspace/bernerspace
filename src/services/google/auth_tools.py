import os
import logging
from typing import Dict, Any, List, Optional
from pydantic import Field
from typing_extensions import Annotated

from fastmcp import FastMCP, Context
from src.middleware.auth import JWTAuthMiddleware, extract_user_from_context
from src.core.storeage_manager import TokenStorageManager
from src.services.google.service import GoogleService
from src.services.google.schemas.google import GoogleToolCall
from fastapi import Request # Import Request for direct access to body
from sqlalchemy.orm import Session # Import Session for type hinting
from src.utils.database import SessionLocal # Import SessionLocal for db session
from starlette.responses import JSONResponse # Import JSONResponse
from src.utils.env_handler import JWT_SECRET as ENV_JWT_SECRET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

jwt_secret = ENV_JWT_SECRET

# Create MCP instance WITHOUT built-in auth
mcp = FastMCP("Google MCP Server")
storageManager = TokenStorageManager()

mcp.add_middleware(JWTAuthMiddleware(
        secret_key=jwt_secret,
        issuer="bernerspace-ecosystem",
        audience="mcp-google-server"
    ))

# ==================== HELPER FUNCTION ====================

# --- Dependency for Database Session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==================== HELPER FUNCTION ====================
async def _get_google_service(ctx: Context):

    """Helper function to get Google service and handle OAuth"""
    user_id = extract_user_from_context(ctx)
    db_session = ctx.state.get("db_session")
    
    if not db_session:
        await ctx.error("Database session not available in context.")
        return {"error": "Database session not available"}, True

    google_service = GoogleService(client_id=user_id, db_session=db_session)
    
    if not google_service.is_authenticated():
        oauth_url = google_service.get_oauth_url()
        await ctx.warning(f"Google OAuth required for user: {user_id}")
        return {
            "requires_auth": True,
            "user_id": user_id,
            "message": "Google OAuth token not found or expired. Please complete the OAuth flow.",
            "oauth_url": oauth_url
        }, True
    
    return google_service, False


@mcp.tool
async def get_google_oauth_url(ctx: Context = None) -> Dict[str, Any]:
    """Get the OAuth URL for Google authorization"""
    user_id = extract_user_from_context(ctx)
    db_session = ctx.state.get("db_session")
    
    if not db_session:
        await ctx.error("Database session not available in context.")
        return {"error": "Database session not available"}

    google_service = GoogleService(client_id=user_id, db_session=db_session)
    return {"oauth_url": google_service.get_oauth_url()}

@mcp.tool
async def check_google_oauth_status(ctx: Context = None) -> Dict[str, Any]:
    """Check if the current user has completed Google OAuth"""
    await ctx.info("Checking Google OAuth status")
    
    try:
        user_id = extract_user_from_context(ctx)
        db_session = ctx.state.get("db_session")
        
        if not db_session:
            await ctx.error("Database session not available in context.")
            return {"error": "Database session not available"}

        google_service = GoogleService(client_id=user_id, db_session=db_session)
        
        if not google_service.is_authenticated():
            oauth_url = google_service.get_oauth_url()
            await ctx.warning(f"No Google OAuth token found for user: {user_id}")
            return {
                "authorized": False,
                "user_id": user_id,
                "message": "No Google OAuth token found or expired. Please complete the OAuth flow.",
                "oauth_url": oauth_url
            }
        
        await ctx.info(f"Google OAuth token found for user: {user_id}")
        return {
            "authorized": True,
            "user_id": user_id,
            "message": "Google OAuth completed successfully."
        }
        
    except Exception as e:
        await ctx.error(f"Error checking Google OAuth status: {str(e)}")
        return {
            "authorized": False,
            "error": str(e),
            "message": "Unable to check Google OAuth status. Please ensure you are authenticated."
        }
