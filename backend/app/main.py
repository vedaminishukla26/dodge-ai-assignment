import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

# ── Global connections ──────────────────────────────────────────────
neo4j_driver = None
pg_engine = None
SessionLocal = None


def get_neo4j_driver():
    return neo4j_driver


def get_pg_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    global neo4j_driver, pg_engine, SessionLocal

    # ── Validate required env vars ──────────────────────────────────
    google_api_key = os.getenv("GOOGLE_API_KEY", "")
    if not google_api_key or google_api_key == "your_gemini_api_key_here":
        raise RuntimeError(
            "Missing GOOGLE_API_KEY – get a free key at https://aistudio.google.com"
        )

    # ── Neo4j connection ────────────────────────────────────────────
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "dodge_ai_2024")
    neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    neo4j_driver.verify_connectivity()
    print("✅ Connected to Neo4j")

    # ── PostgreSQL connection ───────────────────────────────────────
    pg_host = os.getenv("POSTGRES_HOST", "localhost")
    pg_port = os.getenv("POSTGRES_PORT", "5432")
    pg_db = os.getenv("POSTGRES_DB", "dodge_ai")
    pg_user = os.getenv("POSTGRES_USER", "dodge_user")
    pg_pass = os.getenv("POSTGRES_PASSWORD", "dodge_pass_2024")
    pg_url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    pg_engine = create_engine(pg_url)

    # Create tables
    from app.models.chat_models import Base
    Base.metadata.create_all(bind=pg_engine)
    print("✅ Connected to PostgreSQL – tables created")

    SessionLocal = sessionmaker(bind=pg_engine)

    yield  # ── app runs ──

    # ── Shutdown ────────────────────────────────────────────────────
    if neo4j_driver:
        neo4j_driver.close()
        print("🔌 Neo4j driver closed")
    if pg_engine:
        pg_engine.dispose()
        print("🔌 PostgreSQL engine disposed")


# ── FastAPI app ───────────────────────────────────────────────────
app = FastAPI(
    title="Dodge AI",
    description="Graph-based SAP Order-to-Cash query system",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check ──────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "dodge-ai-api"}


# ── Register API routes ──────────────────────────────────────────
from app.routes.chat import router as chat_router  # noqa: E402

app.include_router(chat_router)
