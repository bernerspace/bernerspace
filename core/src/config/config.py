from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URI: str
    DB_NAME: str = "bernerspace"
    GCP_BUCKET: str
    GOOGLE_APPLICATION_CREDENTIALS: str
    CLIENT_ID: str
    CLIENT_SECRET: str 

    class Config:
        pass

settings = Settings()