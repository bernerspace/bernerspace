import aiohttp
import urllib.parse
from datetime import datetime, timezone
from fastmcp import FastMCP
from starlette.responses import JSONResponse
from src.utils.env_handler import SLACK_CLIENT_ID as ENV_SLACK_CLIENT_ID, SLACK_REDIRECT_URI as ENV_SLACK_REDIRECT_URI, SLACK_CLIENT_SECRET as ENV_SLACK_CLIENT_SECRET
from src.core.storeage_manager import TokenStorageManager

slack_client_id = ENV_SLACK_CLIENT_ID
slack_client_secret = ENV_SLACK_CLIENT_SECRET
slack_redirect_uri = ENV_SLACK_REDIRECT_URI

slack_mcp_route = FastMCP("Slack Bot MCP Server")
storageManager=TokenStorageManager()

@slack_mcp_route.custom_route("/slack/oauth/callback", methods=["GET"])
async def slack_oauth_callback(request):
    """Handle Slack OAuth callback with JWT client ID mapping"""
    
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    jwt_client_id = state.split(":")[1] if state and ":" in state else None

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
    


