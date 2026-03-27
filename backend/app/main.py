import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase

# Import the centralized engine and session factory from your updated database.py
from app.database import engine as pg_engine, SessionLocal, init_db

load_dotenv()



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    global neo4j_driver

    # 1. ── Validate required env vars ──────────────────────────────────
    google_api_key = os.getenv("GOOGLE_API_KEY", "")
    if not google_api_key or google_api_key == "your_gemini_api_key_here":
        raise RuntimeError(
            "Missing GOOGLE_API_KEY – get a free key at https://aistudio.google.com"
        )

    # 2. ── Neo4j connection ────────────────────────────────────────────
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "dodge_ai_2024")
    
    try:
        neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        neo4j_driver.verify_connectivity()
        print("✅ Connected to Neo4j Aura")
    except Exception as e:
        print(f"❌ Neo4j connection failed: {e}")
        raise e

    # 3. ── PostgreSQL Initialization ───────────────────────────────────
    try:
        # Uses the logic in database.py to create tables via DATABASE_URL
        init_db()
        print("✅ Connected to Render PostgreSQL – tables created")
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        raise e

    yield  # ── app runs ──

    # 4. ── Shutdown ────────────────────────────────────────────────────
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
from app.routes.chat import router as chat_router
app.include_router(chat_router)