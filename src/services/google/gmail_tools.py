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
async def list_gmail_messages(
    query: Annotated[Optional[str], Field(description="Gmail search query (e.g., 'from:someone@example.com subject:hello')")] = None,
    max_results: Annotated[int, Field(description="Maximum number of messages to return")] = 10,
    ctx: Context = None
) -> Dict[str, Any]:
    """List Gmail messages based on a query."""
    google_service, needs_auth = await _get_google_service(ctx)
    if needs_auth:
        return google_service

    tool_call = GoogleToolCall(
        tool_name="gmail.list_messages",
        parameters={"query": query, "max_results": max_results}
    )
    result = await google_service.handle_tool_call(tool_call)
    return result

@mcp.tool
async def get_gmail_message(
    message_id: Annotated[str, Field(description="The ID of the message to retrieve.")],
    format: Annotated[str, Field(description="The format to return the message in. 'full', 'raw', 'minimal', or 'metadata'.")] = "full",
    ctx: Context = None
) -> Dict[str, Any]:
    """Retrieve a specific Gmail message by its ID."""
    google_service, needs_auth = await _get_google_service(ctx)
    if needs_auth:
        return google_service

    tool_call = GoogleToolCall(
        tool_name="gmail.get_message",
        parameters={"message_id": message_id, "format": format}
    )
    result = await google_service.handle_tool_call(tool_call)
    return result

@mcp.tool
async def send_gmail_message(
    to: Annotated[str, Field(description="Recipient email address(es), comma-separated.")],
    subject: Annotated[str, Field(description="Subject of the email.")],
    body: Annotated[str, Field(description="Body of the email.")],
    cc: Annotated[Optional[str], Field(description="CC recipient email address(es), comma-separated.")] = None,
    bcc: Annotated[Optional[str], Field(description="BCC recipient email address(es), comma-separated.")] = None,
    thread_id: Annotated[Optional[str], Field(description="ID of the thread to add the message to.")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Send an email via Gmail."""
    google_service, needs_auth = await _get_google_service(ctx)
    if needs_auth:
        return google_service

    tool_call = GoogleToolCall(
        tool_name="gmail.send_message",
        parameters={
            "to": to,
            "subject": subject,
            "body": body,
            "cc": cc,
            "bcc": bcc,
            "thread_id": thread_id
        }
    )
    result = await google_service.handle_tool_call(tool_call)
    return result
