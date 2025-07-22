import os
import uvicorn
import logging
import tempfile
import requests # Add this import
from dotenv import load_dotenv
from fastapi import FastAPI
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from src.config.config import settings
from src.models.projects import Project, Version
from src.routes.projects import router as projects_router
from src.routes.uploads import router as uploads_router
from src.routes.auth import router as auth_router 
# Removed: from google.cloud import storage # No longer needed for HTTP download

load_dotenv()
app = FastAPI(title="Bernerpace Sandbox API", version="1.0.0")

@app.get("/")
async def read_root():
    return {"message": "Welcome to Bernerspace Sandbox API!"}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_gcp_credentials_from_url():
    if not settings.GOOGLE_APPLICATION_CREDENTIALS:
        logger.warning("GOOGLE_APPLICATION_CREDENTIALS (URL) is not set. Skipping credential setup.")
        return

    try:
        # Download the JSON content from the URL
        response = requests.get(settings.GOOGLE_APPLICATION_CREDENTIALS)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        json_content = response.text

        # Write to a temporary file
        fd, temp_path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, 'w') as tmp:
            tmp.write(json_content)

        # Set the environment variable
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_path
        logger.info(f"GCP credentials downloaded from URL to {temp_path} and GOOGLE_APPLICATION_CREDENTIALS set.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading GCP credentials from URL: {e}")
        raise
    except Exception as e:
        logger.error(f"Error setting up GCP credentials: {e}")
        raise

@app.on_event("startup")
async def startup_db():
    await setup_gcp_credentials_from_url()
    logger.info(f"Connecting to MongoDB with URI: {settings.MONGO_URI}")
    try:
        client = AsyncIOMotorClient(settings.MONGO_URI)
        db = client[settings.DB_NAME]
        await init_beanie(database=db, document_models=[Project, Version])
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

app.include_router(projects_router)
app.include_router(uploads_router)
app.include_router(auth_router) 


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting Bernerpace Sandbox API on port {port}...")
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        raise