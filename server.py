from typing_extensions import Annotated
from datetime import datetime, timezone
from starlette.responses import JSONResponse
from fastmcp import FastMCP
from src.core.storeage_manager import TokenStorageManager
from src.services.slack.tools import mcp as slack_mcp
from src.services.slack.route import slack_mcp_route as slack_oauth_routes
from src.services.slack.route import slack_oauth_callback
from src.utils.config_handler import is_slack_enabled

storageManager = TokenStorageManager()

# Create the main server
mcp = FastMCP(name="MainServer")


# Mount the Slack MCP server with the "slack" prefix AND the OAuth routes only if Slack is enabled in config
if is_slack_enabled():
    mcp.mount(slack_mcp, prefix="slack")
    mcp.custom_route("/slack/oauth/callback", methods=["GET"])(slack_oauth_callback)


# Custom health check route
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "Slack OAuth MCP Server",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
