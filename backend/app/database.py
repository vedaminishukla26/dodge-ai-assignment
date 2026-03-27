import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models.chat_models import Base


# Strictly use the single connection string
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

# SQLAlchemy 1.4+ requires 'postgresql://' but many providers use 'postgres://'
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # This creates the chat_sessions and chat_messages tables in your Render DB
    Base.metadata.create_all(bind=engine)

def get_session_factory():
    return SessionLocal

def get_pg_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()