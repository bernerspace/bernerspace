"""
Slack Bot API Service using Official Slack SDK
A wrapper around the official slack-sdk for MCP integration
"""

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
import os, urllib.parse
from urllib.parse import urlparse
from pathlib import Path
from src.services.slack.schemas.slack import SlackResponse
from fastmcp import Context
from src.core.storeage_manager import TokenStorageManager
from src.middleware.auth import extract_user_from_context
from src.core.storeage_manager import TokenStorageManager
from fastmcp.server.dependencies import get_context

storageManager = TokenStorageManager()
logger = logging.getLogger(__name__)


class SlackBotAPIService:
    @classmethod
    async def from_context(cls, ctx: Context):
        storageManager = TokenStorageManager()
        jwt_client_id = extract_user_from_context(ctx)
        print("jwt_client_id", jwt_client_id)
        token_data = storageManager.read_token(jwt_client_id)
        access_token = token_data.get("access_token") if token_data else None
        print("access_token", access_token)
        
        if not access_token:
            await ctx.info("No valid Slack OAuth token found. Generating OAuth URL for authorization.")
            # Use the existing get_oauth_url method
            oauth_data = await cls.get_oauth_url()
            # Add the requires_auth flag to indicate authentication is needed
            oauth_data["requires_auth"] = True
            return oauth_data
        
        return cls(access_token)

    @classmethod
    async def get_oauth_url(cls):
        slack_redirect_uri = os.getenv("SLACK_REDIRECT_URI")
        slack_client_id = os.getenv("CLIENT_ID")
        ctx = get_context()
        jwt_payload = ctx.get_state("jwt_payload") if ctx else None
        jwt_client_id = jwt_payload.get('sub') if jwt_payload else ""
        await ctx.info("Generating OAuth URL")
        scopes = ["chat:write", "channels:read", "groups:read", "im:read", "mpim:read"]
        scope_string = ",".join(scopes)
        oauth_url = (
            f"https://slack.com/oauth/v2/authorize?"
            f"client_id={slack_client_id}&"
            f"scope={scope_string}&"
            f"redirect_uri={urllib.parse.quote(slack_redirect_uri)}&"
            f"state=client_id:{jwt_client_id}"
        )
        return {
            "oauth_url": oauth_url,
            "instructions": "Visit this URL to authorize the application with your Slack workspace",
            "callback_url": slack_redirect_uri,
            "scopes": scopes,
            "state": f"client_id:{jwt_client_id}"
        }
    """
    Slack Bot API Service using Official Slack SDK
    Wrapper around AsyncWebClient for MCP integration
    """
    
    def __init__(self, bot_token: str):
        """
        Initialize with bot token using official Slack SDK
        
        Args:
            bot_token: Slack bot token (xoxb-...)
        """
        if not bot_token.startswith('xoxb-'):
            raise ValueError("Bot token must start with 'xoxb-'")
        
        self.bot_token = bot_token
        self.client = AsyncWebClient(token=bot_token)
    
    def _handle_response(self, response) -> SlackResponse:
        """Convert Slack SDK response to our standard format"""
        return SlackResponse(
            ok=response.get("ok", False),
            data=response.data,
            error=response.get("error"),
            warning=response.get("warning")
        )
    
    async def _safe_api_call(self, method_name: str, **kwargs) -> SlackResponse:
        """Safely call Slack API with error handling"""
        try:
            method = getattr(self.client, method_name)
            response = await method(**kwargs)
            return self._handle_response(response)
        except SlackApiError as e:
            logger.error(f"Slack API Error in {method_name}: {e.response['error']}")
            return SlackResponse(
                ok=False,
                data=e.response,
                error=e.response["error"]
            )
        except Exception as e:
            logger.error(f"Unexpected error in {method_name}: {str(e)}")
            return SlackResponse(
                ok=False,
                data={},
                error=str(e)
            )
    
    def _is_url(self, path: str) -> bool:
        """Check if the given string is a URL"""
        try:
            result = urlparse(path)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def _is_file_path(self, path: str) -> bool:
        """Check if the given string is a valid file path"""
        return os.path.isfile(path) or Path(path).exists()
    
    
    async def send_message(
        self, 
        channel: str, 
        text: Optional[str] = None,
        blocks: Optional[List[Dict]] = None,
        attachments: Optional[List[Dict]] = None,
        thread_ts: Optional[str] = None,
        username: Optional[str] = None,
        icon_emoji: Optional[str] = None,
        icon_url: Optional[str] = None
    ) -> SlackResponse:
        """Send a message to a channel"""
        kwargs = {"channel": channel}
        
        if text:
            kwargs["text"] = text
        if blocks:
            kwargs["blocks"] = blocks
        if attachments:
            kwargs["attachments"] = attachments
        if thread_ts:
            kwargs["thread_ts"] = thread_ts
        if username:
            kwargs["username"] = username
        if icon_emoji:
            kwargs["icon_emoji"] = icon_emoji
        if icon_url:
            kwargs["icon_url"] = icon_url
            
        return await self._safe_api_call("chat_postMessage", **kwargs)
    
    async def update_message(
        self,
        channel: str,
        ts: str,
        text: Optional[str] = None,
        blocks: Optional[List[Dict]] = None,
        attachments: Optional[List[Dict]] = None
    ) -> SlackResponse:
        """Update an existing message"""
        kwargs = {"channel": channel, "ts": ts}
        
        if text:
            kwargs["text"] = text
        if blocks:
            kwargs["blocks"] = blocks
        if attachments:
            kwargs["attachments"] = attachments
            
        return await self._safe_api_call("chat_update", **kwargs)
    
    async def delete_message(self, channel: str, ts: str) -> SlackResponse:
        """Delete a message"""
        return await self._safe_api_call("chat_delete", channel=channel, ts=ts)
    
    async def schedule_message(
        self,
        channel: str,
        post_at: int,
        text: Optional[str] = None,
        blocks: Optional[List[Dict]] = None,
        attachments: Optional[List[Dict]] = None
    ) -> SlackResponse:
        """Schedule a message to be sent later"""
        kwargs = {"channel": channel, "post_at": post_at}
        
        if text:
            kwargs["text"] = text
        if blocks:
            kwargs["blocks"] = blocks
        if attachments:
            kwargs["attachments"] = attachments
            
        return await self._safe_api_call("chat_scheduleMessage", **kwargs)
