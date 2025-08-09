import os
import logging
import aiohttp
import urllib.parse
from pathlib import Path
from fastmcp import FastMCP, Context
from typing import List, Optional, Dict, Any, Union
from pydantic import Field
from datetime import datetime, timezone
from typing_extensions import Annotated
from dotenv import load_dotenv
from starlette.responses import JSONResponse
from src.middleware.auth import JWTAuthMiddleware, extract_user_from_context
from src.core.storeage_manager import TokenStorageManager
from services.slack.slack_service import SlackBotAPIService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

jwt_secret = os.getenv("JWT_SECRET")
slack_client_id = os.getenv("CLIENT_ID")
slack_client_secret = os.getenv("CLIENT_SECRET")
slack_redirect_uri = os.getenv("SLACK_REDIRECT_URI")

# File to store OAuth tokens locally
OAUTH_TOKENS_FILE = "oauth_tokens.json"

# Create MCP instance WITHOUT built-in auth
mcp = FastMCP("Slack Bot MCP Server")
storageManager=TokenStorageManager()

mcp.add_middleware(JWTAuthMiddleware(
        secret_key=jwt_secret,
        issuer="bernerspace-ecosystem",
        audience="mcp-slack-server"
    ))

# ==================== HELPER FUNCTION ====================
async def _get_slack_service(ctx: Context):
    """Helper function to get Slack service and handle OAuth"""
    slack_service = await SlackBotAPIService.from_context(ctx)
    
    # Check if OAuth is required
    if isinstance(slack_service, dict) and slack_service.get("requires_auth"):
        return slack_service, True  # Return OAuth info and flag
    
    return slack_service, False


@mcp.tool
async def get_oauth_url(ctx: Context = None) -> Dict[str, Any]:
    """Get the OAuth URL for Slack authorization"""
    return await SlackBotAPIService.get_oauth_url()

@mcp.tool
async def check_oauth_status(ctx: Context = None) -> Dict[str, Any]:
    """Check if the current user has completed OAuth"""
    await ctx.info("Checking OAuth status")
    
    try:
        user_id = extract_user_from_context(ctx)
        token_data = storageManager.read_token(user_id)
        
        if not token_data:
            await ctx.warning(f"No OAuth token found for user: {user_id}")
            oauth_url = f"https://slack.com/oauth/v2/authorize?client_id={slack_client_id}&scope=chat:write,channels:read,groups:read,im:read,mpim:read&redirect_uri={urllib.parse.quote(slack_redirect_uri)}"
            return {
                "authorized": False,
                "user_id": user_id,
                "message": "No OAuth token found. Please complete the OAuth flow.",
                "oauth_url": oauth_url
            }
        
        await ctx.info(f"OAuth token found for user: {user_id}")
        return {
            "authorized": True,
            "user_id": user_id,
            "team_name": token_data.get("team_name"),
            "team_id": token_data.get("team_id"),
            "scopes": token_data.get("scope", "").split(",") if token_data.get("scope") else [],
            "created_at": token_data.get("created_at"),
            "expires_at": token_data.get("expires_at")
        }
        
    except Exception as e:
        await ctx.error(f"Error checking OAuth status: {str(e)}")
        return {
            "authorized": False,
            "error": str(e),
            "message": "Unable to check OAuth status. Please ensure you are authenticated."
        }

# ==================== CHAT & MESSAGING TOOLS ====================

@mcp.tool
async def send_slack_message(
    channel: Annotated[str, Field(description="Channel ID or name (e.g., '#general' or 'C1234567890')")],
    text: Annotated[Optional[str], Field(description="Message text to send")] = None,
    blocks: Annotated[Optional[List[Dict]], Field(description="Slack Block Kit blocks for rich formatting")] = None,
    attachments: Annotated[Optional[List[Dict]], Field(description="Message attachments (legacy)")] = None,
    thread_ts: Annotated[Optional[str], Field(description="Reply in thread to this message timestamp")] = None,
    username: Annotated[Optional[str], Field(description="Custom username for the message")] = None,
    icon_emoji: Annotated[Optional[str], Field(description="Custom emoji icon (e.g., ':robot_face:')")] = None,
    icon_url: Annotated[Optional[str], Field(description="Custom icon URL")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Send a message to a Slack channel with optional rich formatting"""
    if not text and not blocks:
        await ctx.error("Neither text nor blocks provided")
        raise ValueError("Either text or blocks must be provided")
    
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.send_message(
        channel=channel,
        text=text,
        blocks=blocks,
        attachments=attachments,
        thread_ts=thread_ts,
        username=username,
        icon_emoji=icon_emoji,
        icon_url=icon_url
    )
    
    if result.ok:
        await ctx.info(f"Message sent successfully to {channel}")
        return {
            "success": True,
            "channel": result.data.get("channel"),
            "timestamp": result.data.get("ts"),
            "message": "Message sent successfully",
            "permalink": result.data.get("permalink", "")
        }
    else:
        await ctx.error(f"Failed to send message: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def update_slack_message(
    channel: Annotated[str, Field(description="Channel ID where the message is located")],
    ts: Annotated[str, Field(description="Timestamp of the message to update")],
    text: Annotated[Optional[str], Field(description="New message text")] = None,
    blocks: Annotated[Optional[List[Dict]], Field(description="New Slack Block Kit blocks")] = None,
    attachments: Annotated[Optional[List[Dict]], Field(description="New message attachments")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Update an existing Slack message"""
    if not text and not blocks:
        await ctx.error("Neither text nor blocks provided")
        raise ValueError("Either text or blocks must be provided")
    
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.update_message(
        channel=channel,
        ts=ts,
        text=text,
        blocks=blocks,
        attachments=attachments
    )
    
    if result.ok:
        await ctx.info(f"Message updated successfully in {channel}")
        return {
            "success": True,
            "channel": result.data.get("channel"),
            "timestamp": result.data.get("ts"),
            "message": "Message updated successfully"
        }
    else:
        await ctx.error(f"Failed to update message: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def delete_slack_message(
    channel: Annotated[str, Field(description="Channel ID where the message is located")],
    ts: Annotated[str, Field(description="Timestamp of the message to delete")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Delete a Slack message"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.delete_message(channel=channel, ts=ts)
    
    if result.ok:
        await ctx.info(f"Message deleted successfully from {channel}")
        return {
            "success": True,
            "channel": channel,
            "timestamp": ts,
            "message": "Message deleted successfully"
        }
    else:
        await ctx.error(f"Failed to delete message: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def schedule_slack_message(
    channel: Annotated[str, Field(description="Channel ID to send the scheduled message")],
    post_at: Annotated[int, Field(description="Unix timestamp when to post the message")],
    text: Annotated[Optional[str], Field(description="Message text to schedule")] = None,
    blocks: Annotated[Optional[List[Dict]], Field(description="Slack Block Kit blocks for scheduled message")] = None,
    attachments: Annotated[Optional[List[Dict]], Field(description="Message attachments for scheduled message")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Schedule a message to be sent later"""
    if not text and not blocks:
        await ctx.error("Neither text nor blocks provided")
        raise ValueError("Either text or blocks must be provided")
    
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.schedule_message(
        channel=channel,
        post_at=post_at,
        text=text,
        blocks=blocks,
        attachments=attachments
    )
    
    if result.ok:
        await ctx.info(f"Message scheduled successfully for {channel}")
        return {
            "success": True,
            "scheduled_message_id": result.data.get("scheduled_message_id"),
            "channel": result.data.get("channel"),
            "post_at": post_at,
            "message": "Message scheduled successfully"
        }
    else:
        await ctx.error(f"Failed to schedule message: {result.error}")
        return {"success": False, "error": result.error}

# ==================== CHANNEL MANAGEMENT TOOLS ====================

@mcp.tool
async def list_slack_channels(
    exclude_archived: Annotated[bool, Field(description="Exclude archived channels")] = True,
    limit: Annotated[int, Field(description="Number of channels to return (max 100)")] = 100,
    cursor: Annotated[Optional[str], Field(description="Pagination cursor")] = None,
    types: Annotated[str, Field(description="Channel types to include")] = "public_channel,private_channel",
    ctx: Context = None
) -> Dict[str, Any]:
    """List all Slack channels"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.list_channels(
        exclude_archived=exclude_archived,
        limit=limit,
        cursor=cursor,
        types=types
    )
    
    if result.ok:
        channels = result.data.get("channels", [])
        await ctx.info(f"Retrieved {len(channels)} channels")
        return {
            "success": True,
            "channels": channels,
            "total_count": len(channels),
            "cursor": result.data.get("response_metadata", {}).get("next_cursor")
        }
    else:
        await ctx.error(f"Failed to list channels: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def get_slack_channel_info(
    channel: Annotated[str, Field(description="Channel ID to get information about")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Get detailed information about a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.get_channel_info(channel=channel)
    
    if result.ok:
        await ctx.info(f"Retrieved channel info for {channel}")
        return {
            "success": True,
            "channel": result.data.get("channel"),
            "message": "Channel info retrieved successfully"
        }
    else:
        await ctx.error(f"Failed to get channel info: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def create_slack_channel(
    name: Annotated[str, Field(description="Name of the channel to create")],
    is_private: Annotated[bool, Field(description="Whether to create a private channel")] = False,
    ctx: Context = None
) -> Dict[str, Any]:
    """Create a new Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.create_channel(name=name, is_private=is_private)
    
    if result.ok:
        channel_info = result.data.get("channel", {})
        await ctx.info(f"Channel '{name}' created successfully")
        return {
            "success": True,
            "channel": channel_info,
            "channel_id": channel_info.get("id"),
            "message": f"Channel '{name}' created successfully"
        }
    else:
        await ctx.error(f"Failed to create channel: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def join_slack_channel(
    channel: Annotated[str, Field(description="Channel ID to join")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Join a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.join_channel(channel=channel)
    
    if result.ok:
        await ctx.info(f"Successfully joined channel {channel}")
        return {
            "success": True,
            "channel": result.data.get("channel"),
            "message": "Channel joined successfully"
        }
    else:
        await ctx.error(f"Failed to join channel: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def leave_slack_channel(
    channel: Annotated[str, Field(description="Channel ID to leave")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Leave a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.leave_channel(channel=channel)
    
    if result.ok:
        await ctx.info(f"Successfully left channel {channel}")
        return {
            "success": True,
            "message": "Channel left successfully"
        }
    else:
        await ctx.error(f"Failed to leave channel: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def invite_to_slack_channel(
    channel: Annotated[str, Field(description="Channel ID to invite users to")],
    users: Annotated[Union[str, List[str]], Field(description="User ID(s) to invite (comma-separated string or list)")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Invite users to a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.invite_to_channel(channel=channel, users=users)
    
    if result.ok:
        await ctx.info(f"Successfully invited users to channel {channel}")
        return {
            "success": True,
            "channel": result.data.get("channel"),
            "message": "Users invited successfully"
        }
    else:
        await ctx.error(f"Failed to invite users: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def kick_from_slack_channel(
    channel: Annotated[str, Field(description="Channel ID to remove user from")],
    user: Annotated[str, Field(description="User ID to remove from channel")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Remove a user from a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.kick_from_channel(channel=channel, user=user)
    
    if result.ok:
        await ctx.info(f"Successfully removed user {user} from channel {channel}")
        return {
            "success": True,
            "message": "User removed from channel successfully"
        }
    else:
        await ctx.error(f"Failed to remove user: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def set_slack_channel_topic(
    channel: Annotated[str, Field(description="Channel ID to set topic for")],
    topic: Annotated[str, Field(description="New topic for the channel")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Set a Slack channel's topic"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.set_channel_topic(channel=channel, topic=topic)
    
    if result.ok:
        await ctx.info(f"Channel topic set successfully for {channel}")
        return {
            "success": True,
            "topic": result.data.get("topic"),
            "message": "Channel topic set successfully"
        }
    else:
        await ctx.error(f"Failed to set channel topic: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def set_slack_channel_purpose(
    channel: Annotated[str, Field(description="Channel ID to set purpose for")],
    purpose: Annotated[str, Field(description="New purpose for the channel")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Set a Slack channel's purpose"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.set_channel_purpose(channel=channel, purpose=purpose)
    
    if result.ok:
        await ctx.info(f"Channel purpose set successfully for {channel}")
        return {
            "success": True,
            "purpose": result.data.get("purpose"),
            "message": "Channel purpose set successfully"
        }
    else:
        await ctx.error(f"Failed to set channel purpose: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def archive_slack_channel(
    channel: Annotated[str, Field(description="Channel ID to archive")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Archive a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.archive_channel(channel=channel)
    
    if result.ok:
        await ctx.info(f"Channel {channel} archived successfully")
        return {
            "success": True,
            "message": "Channel archived successfully"
        }
    else:
        await ctx.error(f"Failed to archive channel: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def unarchive_slack_channel(
    channel: Annotated[str, Field(description="Channel ID to unarchive")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Unarchive a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.unarchive_channel(channel=channel)
    
    if result.ok:
        await ctx.info(f"Channel {channel} unarchived successfully")
        return {
            "success": True,
            "message": "Channel unarchived successfully"
        }
    else:
        await ctx.error(f"Failed to unarchive channel: {result.error}")
        return {"success": False, "error": result.error}

# ==================== CHANNEL HISTORY TOOLS ====================

@mcp.tool
async def get_slack_channel_history(
    channel: Annotated[str, Field(description="Channel ID to get history from")],
    limit: Annotated[int, Field(description="Number of messages to return (max 100)")] = 100,
    cursor: Annotated[Optional[str], Field(description="Pagination cursor")] = None,
    latest: Annotated[Optional[str], Field(description="Latest message timestamp to include")] = None,
    oldest: Annotated[Optional[str], Field(description="Oldest message timestamp to include")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Get message history from a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.get_channel_history(
        channel=channel,
        limit=limit,
        cursor=cursor,
        latest=latest,
        oldest=oldest
    )
    
    if result.ok:
        messages = result.data.get("messages", [])
        await ctx.info(f"Retrieved {len(messages)} messages from {channel}")
        return {
            "success": True,
            "messages": messages,
            "total_count": len(messages),
            "cursor": result.data.get("response_metadata", {}).get("next_cursor"),
            "has_more": result.data.get("has_more", False)
        }
    else:
        await ctx.error(f"Failed to get channel history: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def get_slack_thread_replies(
    channel: Annotated[str, Field(description="Channel ID where the thread is located")],
    ts: Annotated[str, Field(description="Timestamp of the parent message")],
    limit: Annotated[int, Field(description="Number of replies to return (max 100)")] = 100,
    cursor: Annotated[Optional[str], Field(description="Pagination cursor")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Get replies to a threaded message in Slack"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.get_thread_replies(
        channel=channel,
        ts=ts,
        limit=limit,
        cursor=cursor
    )
    
    if result.ok:
        messages = result.data.get("messages", [])
        await ctx.info(f"Retrieved {len(messages)} thread replies from {channel}")
        return {
            "success": True,
            "messages": messages,
            "total_count": len(messages),
            "cursor": result.data.get("response_metadata", {}).get("next_cursor"),
            "has_more": result.data.get("has_more", False)
        }
    else:
        await ctx.error(f"Failed to get thread replies: {result.error}")
        return {"success": False, "error": result.error}

# ==================== USER MANAGEMENT TOOLS ====================

@mcp.tool
async def list_slack_users(
    limit: Annotated[int, Field(description="Number of users to return (max 100)")] = 100,
    cursor: Annotated[Optional[str], Field(description="Pagination cursor")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """List all users in the Slack workspace"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.list_users(limit=limit, cursor=cursor)
    
    if result.ok:
        users = result.data.get("members", [])
        await ctx.info(f"Retrieved {len(users)} users")
        return {
            "success": True,
            "users": users,
            "total_count": len(users),
            "cursor": result.data.get("response_metadata", {}).get("next_cursor")
        }
    else:
        await ctx.error(f"Failed to list users: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def get_slack_user_info(
    user: Annotated[str, Field(description="User ID to get information about")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Get detailed information about a Slack user"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.get_user_info(user=user)
    
    if result.ok:
        await ctx.info(f"Retrieved user info for {user}")
        return {
            "success": True,
            "user": result.data.get("user"),
            "message": "User info retrieved successfully"
        }
    else:
        await ctx.error(f"Failed to get user info: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def get_slack_user_profile(
    user: Annotated[str, Field(description="User ID to get profile for")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Get a Slack user's profile information"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.get_user_profile(user=user)
    
    if result.ok:
        await ctx.info(f"Retrieved user profile for {user}")
        return {
            "success": True,
            "profile": result.data.get("profile"),
            "message": "User profile retrieved successfully"
        }
    else:
        await ctx.error(f"Failed to get user profile: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def set_slack_user_presence(
    presence: Annotated[str, Field(description="Presence to set (auto or away)")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Set the bot's presence status"""
    if presence not in ["auto", "away"]:
        await ctx.error("Presence must be either 'auto' or 'away'")
        return {"success": False, "error": "Invalid presence value"}
    
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.set_user_presence(presence=presence)
    
    if result.ok:
        await ctx.info(f"Bot presence set to {presence}")
        return {
            "success": True,
            "presence": presence,
            "message": f"Presence set to {presence}"
        }
    else:
        await ctx.error(f"Failed to set presence: {result.error}")
        return {"success": False, "error": result.error}

# ==================== FILE MANAGEMENT TOOLS ====================

@mcp.tool
async def upload_slack_file(
    channels: Annotated[Union[str, List[str]], Field(description="Channel(s) to upload file to")],
    file_source: Annotated[str, Field(description="File source: URL, local path, or text content")],
    filename: Annotated[Optional[str], Field(description="Filename (required for text content)")] = None,
    title: Annotated[Optional[str], Field(description="File title")] = None,
    initial_comment: Annotated[Optional[str], Field(description="Comment to add with file")] = None,
    thread_ts: Annotated[Optional[str], Field(description="Thread timestamp to upload to")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Upload a file to Slack channels (auto-detects URL, path, or content)"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.upload_file(
        channels=channels,
        file_source=file_source,
        filename=filename,
        title=title,
        initial_comment=initial_comment,
        thread_ts=thread_ts
    )
    
    if result.ok:
        file_info = result.data.get("file", {})
        await ctx.info(f"File uploaded successfully: {file_info.get('name', 'Unknown')}")
        return {
            "success": True,
            "file": file_info,
            "file_id": file_info.get("id"),
            "message": "File uploaded successfully"
        }
    else:
        await ctx.error(f"Failed to upload file: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def upload_slack_file_from_url(
    channels: Annotated[Union[str, List[str]], Field(description="Channel(s) to upload file to")],
    file_url: Annotated[str, Field(description="URL of the file to upload")],
    filename: Annotated[Optional[str], Field(description="Custom filename")] = None,
    title: Annotated[Optional[str], Field(description="File title")] = None,
    initial_comment: Annotated[Optional[str], Field(description="Comment to add with file")] = None,
    thread_ts: Annotated[Optional[str], Field(description="Thread timestamp to upload to")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Upload a file from URL to Slack channels"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.upload_file_from_url(
        channels=channels,
        file_url=file_url,
        filename=filename,
        title=title,
        initial_comment=initial_comment,
        thread_ts=thread_ts
    )
    
    if result.ok:
        file_info = result.data.get("file", {})
        await ctx.info(f"File uploaded from URL successfully: {file_info.get('name', 'Unknown')}")
        return {
            "success": True,
            "file": file_info,
            "file_id": file_info.get("id"),
            "message": "File uploaded from URL successfully"
        }
    else:
        await ctx.error(f"Failed to upload file from URL: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def upload_slack_file_content(
    channels: Annotated[Union[str, List[str]], Field(description="Channel(s) to upload file to")],
    content: Annotated[str, Field(description="Text content to upload as file")],
    filename: Annotated[str, Field(description="Filename for the content")],
    title: Annotated[Optional[str], Field(description="File title")] = None,
    initial_comment: Annotated[Optional[str], Field(description="Comment to add with file")] = None,
    thread_ts: Annotated[Optional[str], Field(description="Thread timestamp to upload to")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Upload text content as a file to Slack channels"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.upload_file_content(
        channels=channels,
        content=content,
        filename=filename,
        title=title,
        initial_comment=initial_comment,
        thread_ts=thread_ts
    )
    
    if result.ok:
        file_info = result.data.get("file", {})
        await ctx.info(f"Content uploaded as file successfully: {filename}")
        return {
            "success": True,
            "file": file_info,
            "file_id": file_info.get("id"),
            "message": "Content uploaded as file successfully"
        }
    else:
        await ctx.error(f"Failed to upload content: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def list_slack_files(
    user: Annotated[Optional[str], Field(description="Filter by user ID")] = None,
    channel: Annotated[Optional[str], Field(description="Filter by channel ID")] = None,
    ts_from: Annotated[Optional[str], Field(description="Filter files created after this timestamp")] = None,
    ts_to: Annotated[Optional[str], Field(description="Filter files created before this timestamp")] = None,
    types: Annotated[Optional[str], Field(description="Filter by file types (comma-separated)")] = None,
    count: Annotated[int, Field(description="Number of files to return")] = 100,
    page: Annotated[int, Field(description="Page number")] = 1,
    ctx: Context = None
) -> Dict[str, Any]:
    """List files in the Slack workspace"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.list_files(
        user=user,
        channel=channel,
        ts_from=ts_from,
        ts_to=ts_to,
        types=types,
        count=count,
        page=page
    )
    
    if result.ok:
        files = result.data.get("files", [])
        await ctx.info(f"Retrieved {len(files)} files")
        return {
            "success": True,
            "files": files,
            "total_count": len(files),
            "paging": result.data.get("paging"),
            "message": "Files listed successfully"
        }
    else:
        await ctx.error(f"Failed to list files: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def get_slack_file_info(
    file: Annotated[str, Field(description="File ID to get information about")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Get information about a Slack file"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.get_file_info(file=file)
    
    if result.ok:
        await ctx.info(f"Retrieved file info for {file}")
        return {
            "success": True,
            "file": result.data.get("file"),
            "message": "File info retrieved successfully"
        }
    else:
        await ctx.error(f"Failed to get file info: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def delete_slack_file(
    file: Annotated[str, Field(description="File ID to delete")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Delete a Slack file"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.delete_file(file=file)
    
    if result.ok:
        await ctx.info(f"File {file} deleted successfully")
        return {
            "success": True,
            "message": "File deleted successfully"
        }
    else:
        await ctx.error(f"Failed to delete file: {result.error}")
        return {"success": False, "error": result.error}

# ==================== REACTION TOOLS ====================

@mcp.tool
async def add_slack_reaction(
    name: Annotated[str, Field(description="Emoji name (without colons, e.g., 'thumbsup')")],
    channel: Annotated[str, Field(description="Channel ID where the message is located")],
    timestamp: Annotated[str, Field(description="Timestamp of the message to react to")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Add an emoji reaction to a Slack message"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.add_reaction(name=name, channel=channel, timestamp=timestamp)
    
    if result.ok:
        await ctx.info(f"Reaction '{name}' added successfully")
        return {
            "success": True,
            "reaction": name,
            "message": f"Reaction '{name}' added successfully"
        }
    else:
        await ctx.error(f"Failed to add reaction: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def remove_slack_reaction(
    name: Annotated[str, Field(description="Emoji name (without colons, e.g., 'thumbsup')")],
    channel: Annotated[str, Field(description="Channel ID where the message is located")],
    timestamp: Annotated[str, Field(description="Timestamp of the message to remove reaction from")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Remove an emoji reaction from a Slack message"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.remove_reaction(name=name, channel=channel, timestamp=timestamp)
    
    if result.ok:
        await ctx.info(f"Reaction '{name}' removed successfully")
        return {
            "success": True,
            "reaction": name,
            "message": f"Reaction '{name}' removed successfully"
        }
    else:
        await ctx.error(f"Failed to remove reaction: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def get_slack_reactions(
    channel: Annotated[str, Field(description="Channel ID where the message is located")],
    timestamp: Annotated[str, Field(description="Timestamp of the message to get reactions for")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Get reactions for a Slack message"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.get_reactions(channel=channel, timestamp=timestamp)
    
    if result.ok:
        await ctx.info("Retrieved message reactions successfully")
        return {
            "success": True,
            "message": result.data.get("message"),
            "reactions": result.data.get("message", {}).get("reactions", []),
            "message_text": "Reactions retrieved successfully"
        }
    else:
        await ctx.error(f"Failed to get reactions: {result.error}")
        return {"success": False, "error": result.error}

# ==================== PIN TOOLS ====================

@mcp.tool
async def pin_slack_message(
    channel: Annotated[str, Field(description="Channel ID where the message is located")],
    timestamp: Annotated[str, Field(description="Timestamp of the message to pin")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Pin a message to a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.pin_message(channel=channel, timestamp=timestamp)
    
    if result.ok:
        await ctx.info(f"Message pinned successfully in {channel}")
        return {
            "success": True,
            "message": "Message pinned successfully"
        }
    else:
        await ctx.error(f"Failed to pin message: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def unpin_slack_message(
    channel: Annotated[str, Field(description="Channel ID where the message is located")],
    timestamp: Annotated[str, Field(description="Timestamp of the message to unpin")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Unpin a message from a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.unpin_message(channel=channel, timestamp=timestamp)
    
    if result.ok:
        await ctx.info(f"Message unpinned successfully from {channel}")
        return {
            "success": True,
            "message": "Message unpinned successfully"
        }
    else:
        await ctx.error(f"Failed to unpin message: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def list_slack_pins(
    channel: Annotated[str, Field(description="Channel ID to list pinned items from")],
    ctx: Context = None
) -> Dict[str, Any]:
    """List pinned items in a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.list_pins(channel=channel)
    
    if result.ok:
        pins = result.data.get("items", [])
        await ctx.info(f"Retrieved {len(pins)} pinned items from {channel}")
        return {
            "success": True,
            "pins": pins,
            "total_count": len(pins),
            "message": "Pinned items listed successfully"
        }
    else:
        await ctx.error(f"Failed to list pins: {result.error}")
        return {"success": False, "error": result.error}

# ==================== BOOKMARK TOOLS ====================

@mcp.tool
async def add_slack_bookmark(
    channel_id: Annotated[str, Field(description="Channel ID to add bookmark to")],
    title: Annotated[str, Field(description="Bookmark title")],
    type: Annotated[str, Field(description="Bookmark type (link)")],
    link: Annotated[Optional[str], Field(description="URL for the bookmark")] = None,
    emoji: Annotated[Optional[str], Field(description="Emoji for the bookmark")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Add a bookmark to a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.add_bookmark(
        channel_id=channel_id,
        title=title,
        type=type,
        link=link,
        emoji=emoji
    )
    
    if result.ok:
        bookmark = result.data.get("bookmark", {})
        await ctx.info(f"Bookmark '{title}' added successfully to {channel_id}")
        return {
            "success": True,
            "bookmark": bookmark,
            "bookmark_id": bookmark.get("id"),
            "message": "Bookmark added successfully"
        }
    else:
        await ctx.error(f"Failed to add bookmark: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def remove_slack_bookmark(
    channel_id: Annotated[str, Field(description="Channel ID to remove bookmark from")],
    bookmark_id: Annotated[str, Field(description="Bookmark ID to remove")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Remove a bookmark from a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.remove_bookmark(channel_id=channel_id, bookmark_id=bookmark_id)
    
    if result.ok:
        await ctx.info(f"Bookmark removed successfully from {channel_id}")
        return {
            "success": True,
            "message": "Bookmark removed successfully"
        }
    else:
        await ctx.error(f"Failed to remove bookmark: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def list_slack_bookmarks(
    channel_id: Annotated[str, Field(description="Channel ID to list bookmarks from")],
    ctx: Context = None
) -> Dict[str, Any]:
    """List bookmarks in a Slack channel"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.list_bookmarks(channel_id=channel_id)
    
    if result.ok:
        bookmarks = result.data.get("bookmarks", [])
        await ctx.info(f"Retrieved {len(bookmarks)} bookmarks from {channel_id}")
        return {
            "success": True,
            "bookmarks": bookmarks,
            "total_count": len(bookmarks),
            "message": "Bookmarks listed successfully"
        }
    else:
        await ctx.error(f"Failed to list bookmarks: {result.error}")
        return {"success": False, "error": result.error}

# ==================== USER GROUP TOOLS ====================

@mcp.tool
async def create_slack_usergroup(
    name: Annotated[str, Field(description="Name of the user group")],
    handle: Annotated[Optional[str], Field(description="Handle/mention name for the group")] = None,
    description: Annotated[Optional[str], Field(description="Description of the group")] = None,
    channels: Annotated[Optional[List[str]], Field(description="List of channel IDs to add group to")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Create a new Slack user group"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.create_usergroup(
        name=name,
        handle=handle,
        description=description,
        channels=channels
    )
    
    if result.ok:
        usergroup = result.data.get("usergroup", {})
        await ctx.info(f"User group '{name}' created successfully")
        return {
            "success": True,
            "usergroup": usergroup,
            "usergroup_id": usergroup.get("id"),
            "message": "User group created successfully"
        }
    else:
        await ctx.error(f"Failed to create user group: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def list_slack_usergroups(
    include_disabled: Annotated[bool, Field(description="Include disabled user groups")] = False,
    ctx: Context = None
) -> Dict[str, Any]:
    """List Slack user groups"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.list_usergroups(include_disabled=include_disabled)
    
    if result.ok:
        usergroups = result.data.get("usergroups", [])
        await ctx.info(f"Retrieved {len(usergroups)} user groups")
        return {
            "success": True,
            "usergroups": usergroups,
            "total_count": len(usergroups),
            "message": "User groups listed successfully"
        }
    else:
        await ctx.error(f"Failed to list user groups: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def update_slack_usergroup(
    usergroup: Annotated[str, Field(description="User group ID to update")],
    name: Annotated[Optional[str], Field(description="New name for the group")] = None,
    handle: Annotated[Optional[str], Field(description="New handle for the group")] = None,
    description: Annotated[Optional[str], Field(description="New description for the group")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Update a Slack user group"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.update_usergroup(
        usergroup=usergroup,
        name=name,
        handle=handle,
        description=description
    )
    
    if result.ok:
        updated_usergroup = result.data.get("usergroup", {})
        await ctx.info(f"User group {usergroup} updated successfully")
        return {
            "success": True,
            "usergroup": updated_usergroup,
            "message": "User group updated successfully"
        }
    else:
        await ctx.error(f"Failed to update user group: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def disable_slack_usergroup(
    usergroup: Annotated[str, Field(description="User group ID to disable")],
    ctx: Context = None
) -> Dict[str, Any]:
    """Disable a Slack user group"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.disable_usergroup(usergroup=usergroup)
    
    if result.ok:
        await ctx.info(f"User group {usergroup} disabled successfully")
        return {
            "success": True,
            "message": "User group disabled successfully"
        }
    else:
        await ctx.error(f"Failed to disable user group: {result.error}")
        return {"success": False, "error": result.error}

# ==================== TEAM INFO TOOLS ====================

@mcp.tool
async def get_slack_team_info(ctx: Context = None) -> Dict[str, Any]:
    """Get Slack team information"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.get_team_info()
    
    if result.ok:
        team = result.data.get("team", {})
        await ctx.info("Retrieved team information successfully")
        return {
            "success": True,
            "team": team,
            "message": "Team info retrieved successfully"
        }
    else:
        await ctx.error(f"Failed to get team info: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def get_slack_team_profile(ctx: Context = None) -> Dict[str, Any]:
    """Get Slack team profile fields"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.get_team_profile()
    
    if result.ok:
        profile = result.data.get("profile", {})
        await ctx.info("Retrieved team profile successfully")
        return {
            "success": True,
            "profile": profile,
            "message": "Team profile retrieved successfully"
        }
    else:
        await ctx.error(f"Failed to get team profile: {result.error}")
        return {"success": False, "error": result.error}

# ==================== EMOJI TOOLS ====================

@mcp.tool
async def list_slack_emoji(ctx: Context = None) -> Dict[str, Any]:
    """List custom emoji for the Slack team"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.list_emoji()
    
    if result.ok:
        emoji = result.data.get("emoji", {})
        await ctx.info(f"Retrieved {len(emoji)} custom emoji")
        return {
            "success": True,
            "emoji": emoji,
            "total_count": len(emoji),
            "message": "Custom emoji listed successfully"
        }
    else:
        await ctx.error(f"Failed to list emoji: {result.error}")
        return {"success": False, "error": result.error}

# ==================== DND (Do Not Disturb) TOOLS ====================

@mcp.tool
async def get_slack_dnd_info(
    user: Annotated[Optional[str], Field(description="User ID to get DND info for (defaults to current user)")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Get Do Not Disturb information for a user"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.get_dnd_info(user=user)
    
    if result.ok:
        target = user or "current user"
        await ctx.info(f"Retrieved DND info for {target}")
        return {
            "success": True,
            "dnd_enabled": result.data.get("dnd_enabled"),
            "next_dnd_start_ts": result.data.get("next_dnd_start_ts"),
            "next_dnd_end_ts": result.data.get("next_dnd_end_ts"),
            "snooze_enabled": result.data.get("snooze_enabled"),
            "snooze_endtime": result.data.get("snooze_endtime"),
            "message": "DND info retrieved successfully"
        }
    else:
        await ctx.error(f"Failed to get DND info: {result.error}")
        return {"success": False, "error": result.error}

@mcp.tool
async def get_slack_dnd_team_info(
    users: Annotated[Optional[List[str]], Field(description="List of user IDs to get DND info for")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Get Do Not Disturb information for multiple users"""
    slack_service, needs_auth = await _get_slack_service(ctx)
    if needs_auth:
        return slack_service
    
    result = await slack_service.get_dnd_team_info(users=users)
    
    if result.ok:
        users_info = result.data.get("users", {})
        await ctx.info(f"Retrieved DND info for {len(users_info)} users")
        return {
            "success": True,
            "users": users_info,
            "total_count": len(users_info),
            "message": "Team DND info retrieved successfully"
        }
    else:
        await ctx.error(f"Failed to get team DND info: {result.error}")
        return {"success": False, "error": result.error}

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)