import asyncio
import os
import aiohttp
import urllib.parse
from datetime import datetime, timezone
from fastmcp import FastMCP
from src.services.slack.tools import mcp as slack_mcp
from starlette.responses import JSONResponse
from src.core.storeage_manager import TokenStorageManager
from dotenv import load_dotenv

load_dotenv()

storageManager = TokenStorageManager()

jwt_secret = os.getenv("JWT_SECRET")
slack_client_id = os.getenv("CLIENT_ID")
slack_client_secret = os.getenv("CLIENT_SECRET")
slack_redirect_uri = os.getenv("SLACK_REDIRECT_URI")

# Create the main server
mcp = FastMCP(name="MainServer")

# Mount the Slack MCP server with the "slack" prefix
mcp.mount(slack_mcp, prefix="slack")

# Custom Routes
@mcp.custom_route("/", methods=["GET"])
async def root(request):
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
async def health_check(request):
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "Slack OAuth MCP Server",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "oauth_configured": bool(slack_client_id and slack_client_secret),
        "jwt_configured": bool(jwt_secret)
    })


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
    