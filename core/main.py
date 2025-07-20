import os
import uvicorn
import logging
from dotenv import load_dotenv
from fastapi import FastAPI
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from src.config.config import settings
from src.models.projects import Project, Version
from src.routes.projects import router as projects_router
from src.routes.uploads import router as uploads_router
from src.routes.auth import router as auth_router 
load_dotenv()
app = FastAPI(title="Bernerpace Sandbox API", version="1.0.0")

@app.get("/")
async def read_root():
    return {"message": "Welcome to Bernerspace Sandbox API!"}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_db():
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