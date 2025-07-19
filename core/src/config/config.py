from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URI: str
    DB_NAME: str = "bernerspace"
    GCP_BUCKET: str
    GOOGLE_APPLICATION_CREDENTIALS: str
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str 
    
    class Config:
        env_file = ".env"

settings = Settings()