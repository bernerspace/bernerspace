import asyncio
import uvicorn
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

@app.on_event("startup")
async def startup_db():
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.DB_NAME]
    await init_beanie(database=db, document_models=[Project, Version])

app.include_router(projects_router)
app.include_router(uploads_router)
app.include_router(auth_router) 

if __name__ == "__main__":
    print("Starting Bernerpace Sandbox API...")
    uvicorn.run(
        "main:app",  
        host="0.0.0.0",
        port=8000,
        reload=True
    )