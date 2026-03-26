import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models.chat_models import Base

# Database URL from environment
POSTGRES_USER = os.getenv("POSTGRES_USER", "dodge_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "dodge_pass_2024")
POSTGRES_DB = os.getenv("POSTGRES_DB", "dodge_ai")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db-relational")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
