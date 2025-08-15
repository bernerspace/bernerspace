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

# ==================== GMAIL TOOLS ====================

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

# ==================== CALENDAR TOOLS ====================

@mcp.tool
async def list_google_calendar_events(
    calendar_id: Annotated[str, Field(description="The ID of the calendar to retrieve events from. Use 'primary' for the user's primary calendar.")],
    time_min: Annotated[Optional[str], Field(description="Start time (RFC3339 format, e.g., '2025-08-15T09:00:00Z').")] = None,
    time_max: Annotated[Optional[str], Field(description="End time (RFC3339 format, e.g., '2025-08-15T17:00:00Z').")] = None,
    max_results: Annotated[int, Field(description="Maximum number of events to return.")] = 10,
    single_events: Annotated[bool, Field(description="Whether to expand recurring events into individual instances.")] = True,
    order_by: Annotated[str, Field(description="The order of the events returned in the result. One of: 'startTime', 'updated'.")] = "startTime",
    ctx: Context = None
) -> Dict[str, Any]:
    """List events from a Google Calendar."""
    google_service, needs_auth = await _get_google_service(ctx)
    if needs_auth:
        return google_service

    tool_call = GoogleToolCall(
        tool_name="calendar.list_events",
        parameters={
            "calendar_id": calendar_id,
            "time_min": time_min,
            "time_max": time_max,
            "max_results": max_results,
            "single_events": single_events,
            "order_by": order_by
        }
    )
    result = await google_service.handle_tool_call(tool_call)
    return result

@mcp.tool
async def create_google_calendar_event(
    calendar_id: Annotated[str, Field(description="The ID of the calendar to create the event on. Use 'primary' for the user's primary calendar.")],
    summary: Annotated[str, Field(description="Title of the event.")],
    start_time: Annotated[str, Field(description="Start time of the event (RFC3339 format, e.g., '2025-08-15T09:00:00Z').")],
    end_time: Annotated[str, Field(description="End time of the event (RFC3339 format, e.g., '2025-08-15T10:00:00Z').")],
    description: Annotated[Optional[str], Field(description="Description of the event.")] = None,
    location: Annotated[Optional[str], Field(description="Location of the event.")] = None,
    attendees: Annotated[Optional[List[str]], Field(description="List of attendee emails.")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Create a new event on a Google Calendar."""
    google_service, needs_auth = await _get_google_service(ctx)
    if needs_auth:
        return google_service

    tool_call = GoogleToolCall(
        tool_name="calendar.create_event",
        parameters={
            "calendar_id": calendar_id,
            "summary": summary,
            "start_time": start_time,
            "end_time": end_time,
            "description": description,
            "location": location,
            "attendees": attendees
        }
    )
    result = await google_service.handle_tool_call(tool_call)
    return result
