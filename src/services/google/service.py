import os
import httpx
import json
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.models.oauth_token import OAuthToken
from src.services.google.schemas.google import GoogleToolCall
from src.utils.config_handler import load_config

# --- Google OAuth Configuration ---
# These should be set in your .env file
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("APP_BASE_URL", "http://localhost:8000") + "/oauth/google/callback"

# Google's OAuth2 endpoints
AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class GoogleService:
    """
    Handles Google API interactions, including OAuth and tool calls.
    """

    def __init__(self, client_id: str, db_session: Session):
        self.client_id = client_id
        self.db_session = db_session
        self.config = load_config().get("google", {})

    def _get_oauth_token(self) -> OAuthToken | None:
        """Retrieve the user's Google OAuth token from the database."""
        return self.db_session.query(OAuthToken).filter_by(
            client_id=self.client_id,
            integration_type="google"
        ).first()

    def _is_token_expired(self, token_data: Dict[str, Any], stored_at: datetime) -> bool:
        """Check if the Google OAuth token has expired."""
        expires_in = token_data.get("expires_in", 3600)
        expiration_time = stored_at + timedelta(seconds=expires_in)
        return datetime.now(timezone.utc) >= expiration_time

    async def _refresh_token(self, token_record: OAuthToken) -> None:
        """Refresh the Google OAuth token using the refresh token."""
        token_data = json.loads(token_record.token_json)
        refresh_token = token_data.get("refresh_token")

        if not refresh_token:
            raise ValueError("Refresh token not found. User needs to re-authenticate.")

        data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(TOKEN_URL, data=data)
            response.raise_for_status()
            new_token_data = response.json()

        # Update the existing token record with new access token and potentially new refresh token
        token_data.update(new_token_data)
        token_record.token_json = json.dumps(token_data)
        token_record.stored_at = datetime.now(timezone.utc)
        self.db_session.commit()

    async def is_authenticated(self) -> bool:
        """Check if the user has a valid, non-expired Google OAuth token, refreshing if necessary."""
        token_record = self._get_oauth_token()
        if not token_record:
            return False

        token_data = json.loads(token_record.token_json)
        if self._is_token_expired(token_data, token_record.stored_at):
            try:
                await self._refresh_token(token_record)
                return True  # Token refreshed successfully
            except Exception as e:
                print(f"Error refreshing token: {e}")
                return False  # Refresh failed

        return True

    def get_oauth_url(self) -> str:
        """Generate the Google OAuth authorization URL."""
        if not GOOGLE_CLIENT_ID or not self.config.get("scopes"):
            raise ValueError("Google client ID or scopes are not configured.")

        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(self.config["scopes"]),
            "access_type": "offline",  # Request a refresh token
            "prompt": "consent",
            "state": self.client_id,  # Pass client_id for verification
        }
        return f"{AUTHORIZATION_URL}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> None:
        """Exchange an authorization code for an access token and refresh token."""
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            raise ValueError("Google client credentials are not configured.")

        data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(TOKEN_URL, data=data)
            response.raise_for_status()
            token_data = response.json()

        # Store the token securely in the database
        token_record = self._get_oauth_token()
        if token_record:
            # Update the existing token
            token_record.token_json = json.dumps(token_data)
            token_record.stored_at = datetime.now(timezone.utc)
        else:
            # Create a new token record
            token_record = OAuthToken(
                client_id=self.client_id,
                integration_type="google",
                token_json=json.dumps(token_data),
                stored_at=datetime.now(timezone.utc)
            )
            self.db_session.add(token_record)
        
        self.db_session.commit()

    async def _get_authenticated_service(self, api_name: str, api_version: str):
        token_record = self._get_oauth_token()
        if not token_record:
            raise ValueError("Not authenticated with Google")

        token_data = json.loads(token_record.token_json)
        
        # Construct Credentials explicitly
        creds = Credentials(
            token=token_data.get('access_token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=TOKEN_URL,
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=self.config["scopes"]
        )

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                await self._refresh_token(token_record)
                token_data = json.loads(token_record.token_json) # Reload token data after refresh
                creds = Credentials.from_authorized_user_info(token_data)
            else:
                raise ValueError("Google credentials are not valid or refresh token is missing.")
        
        return build(api_name, api_version, credentials=creds)

    async def _list_gmail_messages(self, query: Optional[str] = None, max_results: int = 10) -> Dict[str, Any]:
        service = await self._get_authenticated_service("gmail", "v1")
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])
        return {"messages": messages}

    async def _get_gmail_message(self, message_id: str, format: str = "full") -> Dict[str, Any]:
        service = await self._get_authenticated_service("gmail", "v1")
        message = service.users().messages().get(userId='me', id=message_id, format=format).execute()
        return {"message": message}

    async def _send_gmail_message(self, to: str, subject: str, body: str, cc: Optional[str] = None, bcc: Optional[str] = None, thread_id: Optional[str] = None) -> Dict[str, Any]:
        import base64
        from email.mime.text import MIMEText

        service = await self._get_authenticated_service("gmail", "v1")

        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        if cc:
            message['cc'] = cc
        if bcc:
            message['bcc'] = bcc

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        body = {'raw': raw_message}
        if thread_id:
            body['threadId'] = thread_id

        send_result = service.users().messages().send(userId='me', body=body).execute()
        return {"status": "success", "message_id": send_result['id']}

    async def _list_google_calendar_events(self, calendar_id: str, time_min: Optional[str] = None, time_max: Optional[str] = None, max_results: int = 10, single_events: bool = True, order_by: str = "startTime") -> Dict[str, Any]:
        service = await self._get_authenticated_service("calendar", "v3")
        events_result = service.events().list(calendarId=calendar_id, timeMin=time_min, timeMax=time_max,
                                              maxResults=max_results, singleEvents=single_events,
                                              orderBy=order_by).execute()
        events = events_result.get('items', [])
        return {"events": events}

    async def _create_google_calendar_event(self, calendar_id: str, summary: str, start_time: str, end_time: str, description: Optional[str] = None, location: Optional[str] = None, attendees: Optional[List[str]] = None) -> Dict[str, Any]:
        service = await self._get_authenticated_service("calendar", "v3")
        
        event = {
            'summary': summary,
            'description': description,
            'location': location,
            'start': {'dateTime': start_time, 'timeZone': 'UTC'},
            'end': {'dateTime': end_time, 'timeZone': 'UTC'},
            'attendees': [{'email': email} for email in attendees] if attendees else [],
        }
        
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        return {"status": "success", "event_id": created_event['id'], "html_link": created_event['htmlLink']}

    async def handle_tool_call(self, tool_call: GoogleToolCall) -> Dict[str, Any]:
        """
        Handle a tool call for the Google service.
        """
        try:
            if tool_call.tool_name == "gmail.list_messages":
                return await self._list_gmail_messages(**tool_call.parameters)
            elif tool_call.tool_name == "gmail.get_message":
                return await self._get_gmail_message(**tool_call.parameters)
            elif tool_call.tool_name == "gmail.send_message":
                return await self._send_gmail_message(**tool_call.parameters)
            elif tool_call.tool_name == "calendar.list_events":
                return await self._list_google_calendar_events(**tool_call.parameters)
            elif tool_call.tool_name == "calendar.create_event":
                return await self._create_google_calendar_event(**tool_call.parameters)
            else:
                return {"status": "error", "message": f"Unknown tool: {tool_call.tool_name}"}

        except Exception as e:
            return {"status": "error", "message": str(e)}
