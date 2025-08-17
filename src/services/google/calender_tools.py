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