from starlette.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from fastapi import Request # Keep Request for direct access to query_params and state

from src.services.google.service import GoogleService
from src.utils.database import SessionLocal

# --- Dependency for Database Session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- OAuth Callback Endpoint for Google ---
async def oauth_google_callback(request: Request):
    """
    Handles the OAuth callback from Google.
    """
    db: Session = next(get_db()) # Manually get db session
    code = request.query_params.get("code")
    state = request.query_params.get("state")  # client_id is in state
    error = request.query_params.get("error")

    if error:
        return JSONResponse(
            status_code=400,
            content={"error": "OAuth failed", "details": error}
        )

    if not code or not state:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid callback request", "details": "Missing code or state."}
        )

    client_id = state # The state parameter should contain the client_id from the JWT
    google_service = GoogleService(client_id=client_id, db_session=db)

    try:
        await google_service.exchange_code_for_token(code)
        # Redirect to a success page or return a success message
        return JSONResponse(
            content={"status": "success", "message": "Successfully authenticated with Google."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to exchange code for token", "details": str(e)}
        )