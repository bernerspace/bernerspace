from typing_extensions import Annotated
from datetime import datetime, timezone
from starlette.responses import JSONResponse
from starlette.requests import Request
from fastmcp import FastMCP, Context
from sqlalchemy.orm import Session # Import Session
from src.core.storeage_manager import TokenStorageManager
import src.utils.database as database # Import the whole module
from src.services.slack.tools import mcp as slack_mcp
from src.services.slack.route import slack_mcp_route as slack_oauth_routes
from src.services.slack.route import slack_oauth_callback
from src.services.google.gmail_tools import mcp as gmail_mcp
from src.services.google.calender_tools import mcp as calendar_mcp
from src.services.google.route import oauth_google_callback
from src.utils.config_handler import is_slack_enabled, is_google_enabled

storageManager = TokenStorageManager()

# Create the main server
mcp = FastMCP(name="MainServer")


# Mount the Slack MCP server with the "slack" prefix AND the OAuth routes only if Slack is enabled in config
if is_slack_enabled():
    mcp.mount(slack_mcp, prefix="slack")
    mcp.custom_route("/slack/oauth/callback", methods=["GET"])(slack_oauth_callback)

from src.services.google.service import GoogleService
from src.services.google.schemas.google import GoogleToolCall
import jwt as pyjwt # Import pyjwt
from src.utils.env_handler import JWT_SECRET as ENV_JWT_SECRET # Import JWT_SECRET

jwt_secret = ENV_JWT_SECRET # Define jwt_secret

# Dependency for Database Session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

if is_google_enabled():
    print("Google integration is enabled. Setting up custom route for Google tools.")

    @mcp.custom_route("/mcp/google", methods=["POST"])
    async def handle_google_tool_call(request: Request):
        db: Session = next(get_db())

        # Manually extract and verify JWT
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "message": "Bearer token missing or invalid."
                }
            )
        token = auth_header.split(" ")[1]
        try:
            payload = pyjwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                issuer="bernerspace-ecosystem", # Ensure this matches your JWT generation
                audience="mcp-google-server" # Ensure this matches your JWT generation
            )
            client_id = payload.get('sub')
            if not client_id:
                raise ValueError("Client ID (sub) not found in JWT payload.")
        except pyjwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"error": "Unauthorized", "message": "Token has expired."})
        except pyjwt.InvalidTokenError as e:
            return JSONResponse(status_code=401, content={"error": "Unauthorized", "message": f"Invalid token: {e}"})
        except ValueError as e:
            return JSONResponse(status_code=400, content={"error": "Bad Request", "message": str(e)})

        google_service = GoogleService(client_id=client_id, db_session=db)

        if not await google_service.is_authenticated():
            oauth_url = google_service.get_oauth_url()
            return JSONResponse(
                status_code=401,
                content={
                    "error": "User not authenticated with Google.",
                    "oauth_url": oauth_url
                }
            )

        tool_call_data = await request.json()
        tool_call = GoogleToolCall(**tool_call_data)

        result = await google_service.handle_tool_call(tool_call)
        return JSONResponse(content=result)

    mcp.custom_route("/oauth/google/callback", methods=["GET"])(oauth_google_callback)




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
