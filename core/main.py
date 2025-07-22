import os
import uvicorn
import logging
import tempfile
from dotenv import load_dotenv
from fastapi import FastAPI
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from src.config.config import settings
from src.models.projects import Project, Version
from src.routes.projects import router as projects_router
from src.routes.uploads import router as uploads_router
from src.routes.auth import router as auth_router 
from google.cloud import storage

load_dotenv()
app = FastAPI(title="Bernerpace Sandbox API", version="1.0.0")

@app.get("/")
async def read_root():
    return {"message": "Welcome to Bernerspace Sandbox API!"}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_gcp_credentials_from_gcs():
    if not settings.GOOGLE_APPLICATION_CREDENTIALS:
        logger.warning("GOOGLE_APPLICATION_CREDENTIALS (GCS path) is not set. Skipping GCS credential setup.")
        return

    try:
        # Parse the GCS path (e.g., gs://your-bucket/your-key.json)
        if not settings.GOOGLE_APPLICATION_CREDENTIALS.startswith("gs://"):
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS must be a gs:// URI")
        
        path_parts = settings.GOOGLE_APPLICATION_CREDENTIALS[len("gs://"):].split("/", 1)
        if len(path_parts) < 2:
            raise ValueError("Invalid GOOGLE_APPLICATION_CREDENTIALS format. Must include bucket and object name.")

        bucket_name = path_parts[0]
        blob_name = path_parts[1]

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Download to a temporary file
        fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(fd) # Close the file descriptor immediately
        blob.download_to_filename(temp_path)

        # Set the environment variable
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_path
        logger.info(f"GCP credentials downloaded from GCS to {temp_path} and GOOGLE_APPLICATION_CREDENTIALS set.")

    except Exception as e:
        logger.error(f"Error setting up GCP credentials from GCS: {e}")
        raise

@app.on_event("startup")
async def startup_db():
    await setup_gcp_credentials_from_gcs()
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