import os
import logging
import aiohttp
import urllib.parse
from pathlib import Path
from fastmcp import FastMCP, Context
from typing import List, Optional, Dict, Any
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

# Custom Routes
@mcp.custom_route("/", methods=["GET"])
async def root():
    """Root endpoint with OAuth flow information"""
    oauth_url = f"https://slack.com/oauth/v2/authorize?client_id={slack_client_id}&scope=chat:write,channels:read,groups:read,im:read,mpim:read&redirect_uri={urllib.parse.quote(slack_redirect_uri)}"
    return JSONResponse({
        "message": "Slack OAuth MCP Server",
        "version": "1.0.0",
        "oauth_url": oauth_url,
        "instructions": "Visit the oauth_url to authorize this application with Slack",
        "callback_url": slack_redirect_uri,
        "status": "Ready for OAuth"
    })

@mcp.custom_route("/slack/oauth/callback", methods=["GET"])
async def slack_oauth_callback(request):
    """Handle Slack OAuth callback with JWT client ID mapping"""
    
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    jwt_client_id = state.split(":")[1] if state and ":" in state else None

    print("OAuth callback received with code:", code)
    print("State parameter:", state)
    print("JWT Client ID:", jwt_client_id)

    print("URL", request.url)

    if error:
        return JSONResponse({
            "error": f"OAuth authorization failed: {error}",
            "message": "Please try the OAuth flow again"
        }, status_code=400)
    if not code:
        return JSONResponse({
            "error": "No authorization code received",
            "message": "OAuth callback missing required code parameter"
        }, status_code=400)
    if not jwt_client_id:
        return JSONResponse({
            "error": "No JWT client ID found in state parameter",
            "message": "Invalid OAuth state parameter"
        }, status_code=400)

    try:
        async with aiohttp.ClientSession() as session:
            data = {
                "client_id": slack_client_id,
                "client_secret": slack_client_secret,
                "code": code,
                "redirect_uri": slack_redirect_uri
            }
            async with session.post("https://slack.com/api/oauth.v2.access", data=data) as response:
                token_response = await response.json()

        if not token_response.get("ok"):
            error_msg = token_response.get("error", "Unknown error")
            return JSONResponse({
                "error": f"OAuth token exchange failed: {error_msg}",
                "details": token_response,
                "message": "Please try the OAuth flow again"
            }, status_code=400)

        authed_user = token_response.get("authed_user", {})
        slack_user_id = authed_user.get("id")
        if not slack_user_id:
            return JSONResponse({
                "error": "No user ID received from Slack",
                "response": token_response,
                "message": "Invalid response from Slack OAuth"
            }, status_code=400)

        team = token_response.get("team", {})
        team_name = team.get("name", "Unknown")
        team_id = team.get("id", "Unknown")

        enhanced_token_data = {
            "access_token": token_response.get("access_token"),
            "token_type": token_response.get("token_type", "Bearer"),
            "scope": token_response.get("scope"),
            "team_id": team_id,
            "team_name": team_name,
            "slack_user_id": slack_user_id,
            "jwt_client_id": jwt_client_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": token_response.get("expires_in", None),
            "bot_user_id": token_response.get("bot_user_id"),
            "enterprise": token_response.get("enterprise"),
            "app_id": token_response.get("app_id"),
            "is_enterprise_install": token_response.get("is_enterprise_install"),
            "mapping_created_at": datetime.now(timezone.utc).isoformat()
        }
        storageManager.write_token(jwt_client_id, enhanced_token_data)
        scopes = token_response.get("scope", "").split(",")
        return JSONResponse({
            "success": True,
            "message": f"Successfully authorized! You can now use Slack tools.",
            "jwt_client_id": jwt_client_id,
            "slack_user_id": slack_user_id,
            "team": team_name,
            "team_id": team_id,
            "scopes": scopes,
            "mapping": {
                "jwt_client_id": jwt_client_id,
                "slack_user_id": slack_user_id,
                "team_name": team_name
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        return JSONResponse({
            "error": f"OAuth callback failed: {str(e)}",
            "message": "Please try the OAuth flow again"
        }, status_code=500)
    


@mcp.custom_route("/health", methods=["GET"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Slack OAuth MCP Server",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "oauth_configured": bool(slack_client_id and slack_client_secret),
        "jwt_configured": bool(jwt_secret)
    }

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
    
    # Get Slack service for the authenticated user
    slack_service = await SlackBotAPIService.from_context(ctx)
    
    # Check if OAuth is required
    if isinstance(slack_service, dict) and slack_service.get("requires_auth"):
        return slack_service  # Return OAuth URL info
    
    # Send the message
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
        ctx.error(f"Failed to send message: {result.error}")


@mcp.tool
async def update_slack_message(
    channel: Annotated[str, Field(description="Channel ID where the message is located")],
    message_ts: Annotated[str, Field(description="Timestamp of the message to update")],
    text: Annotated[Optional[str], Field(description="New text for the message")] = None,
    blocks: Annotated[Optional[List[Dict]], Field(description="New blocks for the message")] = None,
    attachments: Annotated[Optional[List[Dict]], Field(description="New attachments for the message")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """Update an existing Slack message"""
    await ctx.info(f"Updating message {message_ts} in channel: {channel}")
    
    slack_service = await SlackBotAPIService.from_context(ctx)
    result = await slack_service.update_message(
        channel=channel, 
        ts=message_ts, 
        text=text, 
        blocks=blocks, 
        attachments=attachments
    )
    
    if result.ok:
        await ctx.info("Message updated successfully")
        return {
            "success": True,
            "channel": result.data.get("channel"),
            "timestamp": result.data.get("ts"),
            "message": "Message updated successfully"
        }
    else:
        ctx.error(f"Failed to update message: {result.error}")
            

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

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)