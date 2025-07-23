from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URI: str
    DB_NAME: str = "bernerspace"
    GCP_BUCKET: str
    GCP_SECRET_NAME: str # This will hold the name of the Secret Manager secret
    CLIENT_ID: str
    CLIENT_SECRET: str 

    class Config:
        pass # Ensure this line is present, and 'env_file = ".env"' is removed

settings = Settings()