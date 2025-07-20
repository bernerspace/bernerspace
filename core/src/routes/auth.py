# src/routes/auth.py
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from src.config.config import settings

router = APIRouter(tags=["auth"])

@router.get("/callback")
async def github_callback(code: str, state: str):
    """
    Handles the callback from GitHub OAuth.
    Exchanges the temporary code for an access token.
    """
    # Define parameters for the token exchange
    params = {
        "client_id": settings.CLIENT_ID,
        "client_secret": settings.CLIENT_SECRET,
        "code": code
    }
    headers = {"Accept": "application/json"}

    # Exchange the code for an access token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            params=params,
            headers=headers
        )

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get token from GitHub")

    token_data = response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="Access token not found in response")

    # Display the token to the user in a simple HTML page
    html_content = f"""
    <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; flex-direction: column; }}
                .token {{ padding: 20px; border: 2px solid #ccc; border-radius: 8px; background-color: #f9f9f9; word-break: break-all; max-width: 500px; }}
            </style>
        </head>
        <body>
            <h1>✅ Authentication Successful!</h1>
            <p>Copy this token and paste it back into your terminal:</p>
            <div class="token"><b>{access_token}</b></div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)