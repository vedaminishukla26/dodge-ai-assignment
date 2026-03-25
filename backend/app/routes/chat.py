"""
Chat and Graph API routes.

Endpoints:
  POST /api/chat            — query the graph with natural language
  GET  /api/chat/sessions   — list chat sessions
  GET  /api/chat/history/{session_id} — get messages for a session
  GET  /api/graph/data      — full graph for visualization
  GET  /api/graph/node/{node_id} — node details + neighbors
"""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_pg_session
from app.models.chat_models import ChatSession, ChatMessage
from app.services.guardrails import check_guardrail
from app.services.graph_chain import query_graph, get_full_graph, get_node_neighbors

router = APIRouter(prefix="/api", tags=["chat", "graph"])


# ── Request / Response models ──────────────────────────────────────
class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    cypher_query: str = ""
    node_ids: list[str] = []
    session_id: str = ""
    guardrail_blocked: bool = False


# ── POST /api/chat ─────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_pg_session)):
    """Accept a natural-language query, run guardrails + Text-to-Cypher."""

    # 1. Guardrails
    guard = await check_guardrail(req.query)
    if not guard["allowed"]:
        return ChatResponse(
            answer=guard["message"],
            guardrail_blocked=True,
        )

    # 2. Get or create session
    if req.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == req.session_id
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = ChatSession(id=uuid.uuid4(), title=req.query[:80])
        db.add(session)
        db.flush()

    # 3. Persist user message
    user_msg = ChatMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="user",
        content=req.query,
    )
    db.add(user_msg)

    # 4. Query the graph
    try:
        result = await query_graph(req.query)
    except Exception as e:
        result = {
            "answer": f"⚠️ Error processing your query: {str(e)[:300]}",
            "cypher_query": "",
            "raw_results": [],
            "node_ids": [],
        }

    # 5. Persist assistant message
    assistant_msg = ChatMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="assistant",
        content=result["answer"],
        cypher_query=result.get("cypher_query", ""),
        node_ids=json.dumps(result.get("node_ids", [])),
    )
    db.add(assistant_msg)

    # 6. Update session timestamp & title
    session.updated_at = datetime.utcnow()
    db.commit()

    return ChatResponse(
        answer=result["answer"],
        cypher_query=result.get("cypher_query", ""),
        node_ids=result.get("node_ids", []),
        session_id=str(session.id),
    )


# ── GET /api/chat/sessions ─────────────────────────────────────────
@router.get("/chat/sessions")
def list_sessions(db: Session = Depends(get_pg_session)):
    """Return all chat sessions ordered by most recent."""
    sessions = (
        db.query(ChatSession)
        .order_by(ChatSession.updated_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": str(s.id),
            "title": s.title,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in sessions
    ]


# ── GET /api/chat/history/{session_id} ─────────────────────────────
@router.get("/chat/history/{session_id}")
def get_history(session_id: str, db: Session = Depends(get_pg_session)):
    """Return all messages for a given session."""
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "cypher_query": m.cypher_query,
            "node_ids": json.loads(m.node_ids) if m.node_ids else [],
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


# ── GET /api/graph/data ────────────────────────────────────────────
@router.get("/graph/data")
async def graph_data():
    """Return a subset of the full graph for visualization."""
    return await get_full_graph()


# ── GET /api/graph/node/{node_id} ──────────────────────────────────
@router.get("/graph/node/{node_id:path}")
async def node_detail(node_id: str):
    """Return a node's details and its immediate neighbors."""
    result = await get_node_neighbors(node_id)
    if result["node"] is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return result
