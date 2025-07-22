from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URI: str
    DB_NAME: str = "bernerspace"
    GCP_BUCKET: str
    GCP_CREDENTIALS_JSON: str
    CLIENT_ID: str
    CLIENT_SECRET: str 

    class Config:
        env_file = ".env"

settings = Settings()