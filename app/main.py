"""
FastAPI entrypoint — Chatbot Gành Đá Đĩa
Endpoints:
  POST /chat        — Gửi câu hỏi, nhận câu trả lời
  GET  /history     — Xem lịch sử hội thoại
  DELETE /history   — Xóa lịch sử
  GET  /health      — Kiểm tra hệ thống
"""

import time
import uuid
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient

from app.rag.chain import chat
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Cấu hình ──────────────────────────────────────────────────────────────────
MONGO_URI = settings.MONGO_URI
DB_NAME = settings.MONGO_DB_NAME
COLLECTION_HISTORY = settings.COLLECTION_CHAT_HISTORY

app = FastAPI(
    title="Chatbot Gành Đá Đĩa",
    version="1.0.0",
    description="Hệ thống chatbot RAG trả lời câu hỏi về Gành Đá Đĩa, Phú Yên",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = None  # None → tạo session mới


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[dict]
    response_time_ms: float


# ── MongoDB helper ─────────────────────────────────────────────────────────────

def get_collection():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    return client[DB_NAME][COLLECTION_HISTORY]


def load_history(session_id: str) -> list[dict]:
    """Load lịch sử hội thoại từ MongoDB."""
    try:
        col = get_collection()
        session = col.find_one({"session_id": session_id})
        if session:
            return session.get("messages", [])
    except Exception as e:
        logger.warning(f"Không load được history: {e}")
    return []


def save_history(session_id: str, messages: list[dict]):
    """Lưu lịch sử hội thoại vào MongoDB."""
    try:
        col = get_collection()
        col.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "session_id": session_id,
                    "messages": messages,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "created_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"Không lưu được history: {e}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Kiểm tra hệ thống."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        mongo_status = "ok"
    except Exception:
        mongo_status = "error"

    return {
        "status": "ok",
        "mongodb": mongo_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """
    Nhận câu hỏi → RAG → trả lời.
    Nếu không có session_id thì tạo mới.
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống.")

    # Tạo hoặc dùng session có sẵn
    session_id = req.session_id or str(uuid.uuid4())

    # Load lịch sử
    history = load_history(session_id)

    # Gọi RAG chain
    start = time.time()
    result = chat(query=req.message, history=history)
    elapsed_ms = round((time.time() - start) * 1000, 1)

    # Cập nhật lịch sử
    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": result["answer"]})
    save_history(session_id, history)

    logger.info(f"✅ [{session_id[:8]}] '{req.message[:40]}' → {elapsed_ms}ms")

    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        sources=result["sources"],
        response_time_ms=elapsed_ms,
    )


@app.get("/history/{session_id}")
def get_history(session_id: str):
    """Xem lịch sử hội thoại của một session."""
    messages = load_history(session_id)
    return {"session_id": session_id, "messages": messages, "total": len(messages)}


@app.delete("/history/{session_id}")
def delete_history(session_id: str):
    """Xóa lịch sử hội thoại của một session."""
    try:
        col = get_collection()
        col.delete_one({"session_id": session_id})
        return {"message": f"Đã xóa lịch sử session {session_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    return {
        "name": "Chatbot Gành Đá Đĩa",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
