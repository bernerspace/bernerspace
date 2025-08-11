import os
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from src.utils.env_handler import DATABASE_URL as ENV_DATABASE_URL

# Engine and Session setup (defaults to local Postgres)
DATABASE_URL = ENV_DATABASE_URL

# Prefer psycopg v3 driver if not specified
if DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)