"""
Slack Bot API Service using Official Slack SDK
A wrapper around the official slack-sdk for MCP integration
"""

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
import logging
import httpx
import io
import os, urllib.parse
from urllib.parse import urlparse
from pathlib import Path
from src.services.slack.schemas.slack import SlackResponse
from fastmcp import Context
from src.core.storeage_manager import TokenStorageManager
from src.middleware.auth import extract_user_from_context
from fastmcp.server.dependencies import get_context

storageManager = TokenStorageManager()
logger = logging.getLogger(__name__)


class SlackBotAPIService:
    @classmethod
    async def from_context(cls, ctx: Context):
        storageManager = TokenStorageManager()
        jwt_client_id = extract_user_from_context(ctx)
        print("jwt_client_id", jwt_client_id)

        # If there is no client id (JWT missing), instruct to add JWT token
        if not jwt_client_id:
            await ctx.error("Missing JWT token. Please add JWT token.")
            return {
                "requires_auth": True,
                "error": "Missing JWT token. Please add JWT token.",
                "message": "Add a valid JWT token in the Authorization header: 'Bearer <token>'"
            }

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

    # ==================== CHANNELS ====================
    
    async def list_channels(
        self,
        exclude_archived: bool = True,
        limit: int = 100,
        cursor: Optional[str] = None,
        types: str = "public_channel,private_channel"
    ) -> SlackResponse:
        """List all channels"""
        kwargs = {
            "exclude_archived": exclude_archived,
            "limit": limit,
            "types": types
        }
        if cursor:
            kwargs["cursor"] = cursor
            
        return await self._safe_api_call("conversations_list", **kwargs)
    
    async def get_channel_info(self, channel: str) -> SlackResponse:
        """Get information about a channel"""
        return await self._safe_api_call("conversations_info", channel=channel)
    
    async def create_channel(
        self,
        name: str,
        is_private: bool = False
    ) -> SlackResponse:
        """Create a new channel"""
        return await self._safe_api_call("conversations_create", name=name, is_private=is_private)
    
    async def join_channel(self, channel: str) -> SlackResponse:
        """Join a channel"""
        return await self._safe_api_call("conversations_join", channel=channel)
    
    async def leave_channel(self, channel: str) -> SlackResponse:
        """Leave a channel"""
        return await self._safe_api_call("conversations_leave", channel=channel)
    
    async def invite_to_channel(self, channel: str, users: Union[str, List[str]]) -> SlackResponse:
        """Invite users to a channel"""
        if isinstance(users, list):
            users = ",".join(users)
        return await self._safe_api_call("conversations_invite", channel=channel, users=users)
    
    async def kick_from_channel(self, channel: str, user: str) -> SlackResponse:
        """Remove a user from a channel"""
        return await self._safe_api_call("conversations_kick", channel=channel, user=user)
    
    async def set_channel_topic(self, channel: str, topic: str) -> SlackResponse:
        """Set channel topic"""
        return await self._safe_api_call("conversations_setTopic", channel=channel, topic=topic)
    
    async def set_channel_purpose(self, channel: str, purpose: str) -> SlackResponse:
        """Set channel purpose"""
        return await self._safe_api_call("conversations_setPurpose", channel=channel, purpose=purpose)
    
    async def archive_channel(self, channel: str) -> SlackResponse:
        """Archive a channel"""
        return await self._safe_api_call("conversations_archive", channel=channel)
    
    async def unarchive_channel(self, channel: str) -> SlackResponse:
        """Unarchive a channel"""
        return await self._safe_api_call("conversations_unarchive", channel=channel)

    # ==================== CHANNEL HISTORY ====================
    
    async def get_channel_history(
        self,
        channel: str,
        limit: int = 100,
        cursor: Optional[str] = None,
        latest: Optional[str] = None,
        oldest: Optional[str] = None
    ) -> SlackResponse:
        """Get channel message history"""
        kwargs = {"channel": channel, "limit": limit}
        
        if cursor:
            kwargs["cursor"] = cursor
        if latest:
            kwargs["latest"] = latest
        if oldest:
            kwargs["oldest"] = oldest
            
        return await self._safe_api_call("conversations_history", **kwargs)
    
    async def get_thread_replies(
        self,
        channel: str,
        ts: str,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> SlackResponse:
        """Get replies to a threaded message"""
        kwargs = {"channel": channel, "ts": ts, "limit": limit}
        
        if cursor:
            kwargs["cursor"] = cursor
            
        return await self._safe_api_call("conversations_replies", **kwargs)

    # ==================== USERS ====================
    
    async def list_users(
        self,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> SlackResponse:
        """List all users in workspace"""
        kwargs = {"limit": limit}
        if cursor:
            kwargs["cursor"] = cursor
            
        return await self._safe_api_call("users_list", **kwargs)
    
    async def get_user_info(self, user: str) -> SlackResponse:
        """Get information about a user"""
        return await self._safe_api_call("users_info", user=user)
    
    async def get_user_profile(self, user: str) -> SlackResponse:
        """Get user's profile information"""
        return await self._safe_api_call("users_profile_get", user=user)
    
    async def set_user_presence(self, presence: str) -> SlackResponse:
        """Set bot's presence (auto or away)"""
        return await self._safe_api_call("users_setPresence", presence=presence)

    # ==================== FILES (DYNAMIC UPLOAD) ====================
    
    async def upload_file(
        self,
        channels: Union[str, List[str]],
        file_source: str,
        filename: Optional[str] = None,
        title: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None
    ) -> SlackResponse:
        """
        Dynamic file upload - automatically detects if source is URL, file path, or content
        
        Args:
            channels: Channel(s) to upload to
            file_source: Can be URL, local file path, or text content
            filename: Optional filename (required for text content)
            title: File title
            initial_comment: Comment to add with file
            thread_ts: Thread timestamp if uploading to thread
        """
        if isinstance(channels, list):
            channels = ",".join(channels)
        
        # Auto-detect source type and route to appropriate method
        if self._is_url(file_source):
            return await self._upload_from_url(
                channels, file_source, filename, title, initial_comment, thread_ts
            )
        elif self._is_file_path(file_source):
            return await self._upload_from_path(
                channels, file_source, filename, title, initial_comment, thread_ts
            )
        else:
            # Treat as text content
            if not filename:
                return SlackResponse(
                    ok=False,
                    data={},
                    error="filename is required when uploading text content"
                )
            return await self._upload_content(
                channels, file_source, filename, title, initial_comment, thread_ts
            )
    
    async def _upload_from_url(
        self,
        channels: str,
        file_url: str,
        filename: Optional[str],
        title: Optional[str],
        initial_comment: Optional[str],
        thread_ts: Optional[str]
    ) -> SlackResponse:
        """Download file from URL and upload to Slack"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(file_url)
                response.raise_for_status()
                
                # Get filename from URL if not provided
                if not filename:
                    parsed_url = urlparse(file_url)
                    filename = os.path.basename(parsed_url.path)
                    if not filename or '.' not in filename:
                        # Try to get extension from content-type
                        content_type = response.headers.get('content-type', '')
                        if 'pdf' in content_type:
                            filename = "downloaded_file.pdf"
                        elif 'image' in content_type:
                            filename = "downloaded_image.jpg"
                        else:
                            filename = "downloaded_file"
                
                # Create file-like object from downloaded content
                file_data = io.BytesIO(response.content)
                
                kwargs = {
                    "channel": channels,
                    "file": file_data,
                    "filename": filename
                }
                
                if title:
                    kwargs["title"] = title
                else:
                    kwargs["title"] = f"File from {file_url}"
                    
                if initial_comment:
                    kwargs["initial_comment"] = initial_comment
                if thread_ts:
                    kwargs["thread_ts"] = thread_ts
                
                return await self._safe_api_call("files_upload_v2", **kwargs)
                
        except httpx.HTTPError as e:
            return SlackResponse(
                ok=False,
                data={},
                error=f"Failed to download file from URL: {str(e)}"
            )
        except Exception as e:
            return SlackResponse(
                ok=False,
                data={},
                error=f"Upload failed: {str(e)}"
            )
    
    async def _upload_from_path(
        self,
        channels: str,
        file_path: str,
        filename: Optional[str],
        title: Optional[str],
        initial_comment: Optional[str],
        thread_ts: Optional[str]
    ) -> SlackResponse:
        """Upload file from local file system path"""
        try:
            if not filename:
                filename = os.path.basename(file_path)
            
            kwargs = {
                "channel": channels,
                "file": file_path,
                "filename": filename
            }
            
            if title:
                kwargs["title"] = title
            else:
                kwargs["title"] = f"File: {filename}"
                
            if initial_comment:
                kwargs["initial_comment"] = initial_comment
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            
            return await self._safe_api_call("files_upload_v2", **kwargs)
            
        except Exception as e:
            return SlackResponse(
                ok=False,
                data={},
                error=f"Failed to upload file from path: {str(e)}"
            )
    
    async def _upload_content(
        self,
        channels: str,
        content: str,
        filename: str,
        title: Optional[str],
        initial_comment: Optional[str],
        thread_ts: Optional[str]
    ) -> SlackResponse:
        """Upload text content as a file"""
        try:
            # Create file-like object from content
            file_data = io.BytesIO(content.encode('utf-8'))
            
            kwargs = {
                "channel": channels,
                "file": file_data,
                "filename": filename
            }
            
            if title:
                kwargs["title"] = title
            else:
                kwargs["title"] = f"Text file: {filename}"
                
            if initial_comment:
                kwargs["initial_comment"] = initial_comment
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            
            return await self._safe_api_call("files_upload_v2", **kwargs)
            
        except Exception as e:
            return SlackResponse(
                ok=False,
                data={},
                error=f"Failed to upload content: {str(e)}"
            )
    
    # Convenience methods for specific upload types
    async def upload_file_from_url(
        self,
        channels: Union[str, List[str]],
        file_url: str,
        filename: Optional[str] = None,
        title: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None
    ) -> SlackResponse:
        """Upload file from URL (explicit method)"""
        return await self.upload_file(channels, file_url, filename, title, initial_comment, thread_ts)
    
    async def upload_file_from_path(
        self,
        channels: Union[str, List[str]],
        file_path: str,
        filename: Optional[str] = None,
        title: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None
    ) -> SlackResponse:
        """Upload file from local path (explicit method)"""
        return await self.upload_file(channels, file_path, filename, title, initial_comment, thread_ts)
    
    async def upload_file_content(
        self,
        channels: Union[str, List[str]],
        content: str,
        filename: str,
        title: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None
    ) -> SlackResponse:
        """Upload text content as file (explicit method)"""
        return await self.upload_file(channels, content, filename, title, initial_comment, thread_ts)
    
    async def list_files(
        self,
        user: Optional[str] = None,
        channel: Optional[str] = None,
        ts_from: Optional[str] = None,
        ts_to: Optional[str] = None,
        types: Optional[str] = None,
        count: int = 100,
        page: int = 1
    ) -> SlackResponse:
        """List files in workspace"""
        kwargs = {"count": count, "page": page}
        
        if user:
            kwargs["user"] = user
        if channel:
            kwargs["channel"] = channel
        if ts_from:
            kwargs["ts_from"] = ts_from
        if ts_to:
            kwargs["ts_to"] = ts_to
        if types:
            kwargs["types"] = types
            
        return await self._safe_api_call("files_list", **kwargs)
    
    async def get_file_info(self, file: str) -> SlackResponse:
        """Get information about a file"""
        return await self._safe_api_call("files_info", file=file)
    
    async def delete_file(self, file: str) -> SlackResponse:
        """Delete a file"""
        return await self._safe_api_call("files_delete", file=file)

    # ==================== REACTIONS ====================
    
    async def add_reaction(self, name: str, channel: str, timestamp: str) -> SlackResponse:
        """Add emoji reaction to a message"""
        return await self._safe_api_call("reactions_add", name=name, channel=channel, timestamp=timestamp)
    
    async def remove_reaction(self, name: str, channel: str, timestamp: str) -> SlackResponse:
        """Remove emoji reaction from a message"""
        return await self._safe_api_call("reactions_remove", name=name, channel=channel, timestamp=timestamp)
    
    async def get_reactions(self, channel: str, timestamp: str) -> SlackResponse:
        """Get reactions for a message"""
        return await self._safe_api_call("reactions_get", channel=channel, timestamp=timestamp)

    # ==================== PINS ====================
    
    async def pin_message(self, channel: str, timestamp: str) -> SlackResponse:
        """Pin a message to channel"""
        return await self._safe_api_call("pins_add", channel=channel, timestamp=timestamp)
    
    async def unpin_message(self, channel: str, timestamp: str) -> SlackResponse:
        """Unpin a message from channel"""
        return await self._safe_api_call("pins_remove", channel=channel, timestamp=timestamp)
    
    async def list_pins(self, channel: str) -> SlackResponse:
        """List pinned items in channel"""
        return await self._safe_api_call("pins_list", channel=channel)

    # ==================== BOOKMARKS ====================
    
    async def add_bookmark(
        self,
        channel_id: str,
        title: str,
        type: str,
        link: Optional[str] = None,
        emoji: Optional[str] = None
    ) -> SlackResponse:
        """Add a bookmark to channel"""
        kwargs = {
            "channel_id": channel_id,
            "title": title,
            "type": type
        }
        if link:
            kwargs["link"] = link
        if emoji:
            kwargs["emoji"] = emoji
            
        return await self._safe_api_call("bookmarks_add", **kwargs)
    
    async def remove_bookmark(self, channel_id: str, bookmark_id: str) -> SlackResponse:
        """Remove a bookmark from channel"""
        return await self._safe_api_call("bookmarks_remove", channel_id=channel_id, bookmark_id=bookmark_id)
    
    async def list_bookmarks(self, channel_id: str) -> SlackResponse:
        """List bookmarks in channel"""
        return await self._safe_api_call("bookmarks_list", channel_id=channel_id)

    # ==================== USER GROUPS ====================
    
    async def create_usergroup(
        self,
        name: str,
        handle: Optional[str] = None,
        description: Optional[str] = None,
        channels: Optional[List[str]] = None
    ) -> SlackResponse:
        """Create a user group"""
        kwargs = {"name": name}
        
        if handle:
            kwargs["handle"] = handle
        if description:
            kwargs["description"] = description
        if channels:
            kwargs["channels"] = ",".join(channels)
            
        return await self._safe_api_call("usergroups_create", **kwargs)
    
    async def list_usergroups(self, include_disabled: bool = False) -> SlackResponse:
        """List user groups"""
        return await self._safe_api_call("usergroups_list", include_disabled=include_disabled)
    
    async def update_usergroup(
        self,
        usergroup: str,
        name: Optional[str] = None,
        handle: Optional[str] = None,
        description: Optional[str] = None
    ) -> SlackResponse:
        """Update a user group"""
        kwargs = {"usergroup": usergroup}
        
        if name:
            kwargs["name"] = name
        if handle:
            kwargs["handle"] = handle
        if description:
            kwargs["description"] = description
            
        return await self._safe_api_call("usergroups_update", **kwargs)
    
    async def disable_usergroup(self, usergroup: str) -> SlackResponse:
        """Disable a user group"""
        return await self._safe_api_call("usergroups_disable", usergroup=usergroup)

    # ==================== TEAM INFO ====================
    
    async def get_team_info(self) -> SlackResponse:
        """Get team information"""
        return await self._safe_api_call("team_info")
    
    async def get_team_profile(self) -> SlackResponse:
        """Get team profile fields"""
        return await self._safe_api_call("team_profile_get")

    # ==================== EMOJI ====================
    
    async def list_emoji(self) -> SlackResponse:
        """List custom emoji for team"""
        return await self._safe_api_call("emoji_list")

    # ==================== DND (Do Not Disturb) ====================
    
    async def get_dnd_info(self, user: Optional[str] = None) -> SlackResponse:
        """Get Do Not Disturb info for user"""
        kwargs = {}
        if user:
            kwargs["user"] = user
            
        return await self._safe_api_call("dnd_info", **kwargs)
    
    async def get_dnd_team_info(self, users: Optional[List[str]] = None) -> SlackResponse:
        """Get DND info for multiple users"""
        kwargs = {}
        if users:
            kwargs["users"] = ",".join(users)
            
        return await self._safe_api_call("dnd_teamInfo", **kwargs)