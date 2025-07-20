import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer_scheme = HTTPBearer()

async def get_current_user_email(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    """
    Validates the Bearer token and fetches the user's primary email from GitHub.
    
    This function acts as a dependency in FastAPI routes to protect them
    and retrieve the authenticated user's email.
    """
    token = creds.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    github_api_url = "https://api.github.com/user/emails"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(github_api_url, headers=headers)
        
        response.raise_for_status()

        emails = response.json()
        
        for email_info in emails:
            if email_info.get("primary") and email_info.get("verified"):
                return email_info["email"]
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No verified primary email found on GitHub account."
        )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired GitHub token."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify identity with GitHub."
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during authentication."
        )

