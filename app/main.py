"""
FastAPI entrypoint — Chatbot Gành Đá Đĩa v2.0
  /         → Chat UI
  /admin/ui → Admin UI
  /admin/*  → Admin API endpoints
"""

import time
import uuid
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from app.rag.pipeline import rag_chat, rag_chat_stream

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient

from app.core.config import settings
from app.api.admin import router as admin_router

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description="Hệ thống RAG Chatbot về Gành Đá Đĩa, Phú Yên. Powered by LangChain + MongoDB + Ollama.",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"❌ Lỗi validation: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)


# ── Schemas ────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: List[Dict[str, Any]]
    query_vector_preview: List[float]
    query_vector_dim: int
    search_time_ms: float
    cached: bool
    response_time_ms: float


# ── MongoDB helpers ────────────────────────────────────────────────────────────


def _get_history_col():
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=3000)
    return client[settings.MONGO_DB_NAME][settings.COLLECTION_CHAT_HISTORY]


def load_history(session_id: str) -> list[dict]:
    try:
        col = _get_history_col()
        doc = col.find_one({"session_id": session_id})
        return doc.get("messages", []) if doc else []
    except Exception as e:
        logger.warning(f"Không load được history: {e}")
        return []


def save_history(session_id: str, messages: list[dict]):
    try:
        col = _get_history_col()
        col.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "session_id": session_id,
                    "messages": messages,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"Không lưu được history: {e}")


# ── Endpoints ──────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    """Kiểm tra trạng thái các service."""
    try:
        client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        mongo_ok = True
        total_chunks = client[settings.MONGO_DB_NAME][
            settings.COLLECTION_DOCUMENTS
        ].count_documents({})
        total_files = client[settings.MONGO_DB_NAME][
            settings.COLLECTION_UPLOADED_FILES
        ].count_documents({})
    except Exception:
        mongo_ok = False
        total_chunks = 0
        total_files = 0

    return {
        "status": "ok",
        "mongodb": "ok" if mongo_ok else "error",
        "total_chunks": total_chunks,
        "total_files": total_files,
        "llm_model": settings.OLLAMA_LLM_MODEL,
        "embed_model": settings.OLLAMA_EMBED_MODEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """Endpoint chat chính — RAG với LangChain."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống.")

    session_id = req.session_id or str(uuid.uuid4())
    history = load_history(session_id)

    start = time.time()
    result = rag_chat(query=req.message, history=history)
    elapsed_ms = round((time.time() - start) * 1000, 1)

    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": result["answer"]})
    save_history(session_id, history)

    logger.info(
        f"✅ [{session_id[:8]}] '{req.message[:40]}' → {elapsed_ms}ms (cached={result['cached']})"
    )

    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        sources=result["sources"],
        query_vector_preview=result["query_vector"],
        query_vector_dim=result["query_vector_dim"],
        search_time_ms=result["search_time_ms"],
        cached=result["cached"],
        response_time_ms=elapsed_ms,
    )


@app.post("/chat/stream")
def chat_stream_endpoint(req: ChatRequest):
    """Endpoint chat streaming — RAG với LangChain."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống.")

    session_id = req.session_id or str(uuid.uuid4())
    history = load_history(session_id)

    return StreamingResponse(
        rag_chat_stream(query=req.message, session_id=session_id, history=history),
        media_type="text/event-stream",
    )


@app.get("/sessions")
def get_all_sessions():
    try:
        col = _get_history_col()
        # Find all session docs, project needed fields, sort descending by update time
        docs = col.find({}, {"session_id": 1, "updated_at": 1, "messages": {"$slice": 1}}).sort("updated_at", -1)
        sessions = []
        for d in docs:
            # Generate a title from the first message
            if "messages" in d and len(d["messages"]) > 0:
                first_msg = d["messages"][0]["content"]
                title = first_msg[:35] + "..." if len(first_msg) > 35 else first_msg
            else:
                title = "Đoạn chat mới"
            
            sessions.append({
                "id": d["session_id"],
                "title": title
            })
        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"Lỗi load sessions: {e}")
        return {"sessions": []}

@app.get("/history/{session_id}")
def get_history(session_id: str):
    messages = load_history(session_id)
    return {"session_id": session_id, "messages": messages, "total": len(messages)}


@app.delete("/history/{session_id}")
def delete_history(session_id: str):
    try:
        col = _get_history_col()
        col.delete_one({"session_id": session_id})
        return {"message": f"Đã xóa lịch sử session {session_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── HTML pages ─────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
def chat_page():
    p = Path(__file__).parent.parent / "static" / "chat.html"
    return (
        p.read_text(encoding="utf-8")
        if p.exists()
        else HTMLResponse("<h2>Chưa có chat.html — tạo file static/chat.html</h2>")
    )


@app.get("/admin/ui", response_class=HTMLResponse)
def admin_ui_page():
    p = Path(__file__).parent.parent / "static" / "admin.html"
    return (
        p.read_text(encoding="utf-8")
        if p.exists()
        else HTMLResponse("<h2>Chưa có admin.html — tạo file static/admin.html</h2>")
    )
