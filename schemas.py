"""
Pydantic schemas cho tất cả collections trong MongoDB.
- DocumentChunk  : một đoạn văn bản đã được chunk + embed
- ChatMessage    : một tin nhắn trong lịch sử hội thoại
- ChatSession    : một phiên hội thoại
- ChatRequest    : request body từ client
- ChatResponse   : response trả về client
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId


# ── Helpers ──────────────────────────────────────────────────────────────────

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PyObjectId(str):
    """Cho phép dùng ObjectId của MongoDB với Pydantic v2."""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError(f"Invalid ObjectId: {v}")
        return str(v)


# ── Enum ──────────────────────────────────────────────────────────────────────

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# ── Collection: documents ─────────────────────────────────────────────────────

class DocumentChunk(BaseModel):
    """
    Một đoạn (chunk) văn bản về Gành Đá Đĩa đã được lưu vào MongoDB.

    Mỗi document trong collection 'documents' tương ứng một chunk.
    Vector embedding được lưu dưới dạng list[float] để dùng với
    MongoDB Atlas Vector Search ($vectorSearch).
    """
    doc_id: str = Field(
        description="ID duy nhất của chunk, ví dụ: ganh_da_dia_001_chunk_0"
    )
    content: str = Field(
        description="Nội dung văn bản của chunk"
    )
    embedding: list[float] = Field(
        default_factory=list,
        description=f"Vector embedding ({768} chiều từ nomic-embed-text)"
    )
    metadata: "ChunkMetadata" = Field(
        default_factory=lambda: ChunkMetadata(),
        description="Metadata bổ sung cho chunk"
    )
    created_at: datetime = Field(default_factory=utc_now)

    model_config = {"populate_by_name": True}


class ChunkMetadata(BaseModel):
    """Metadata đính kèm mỗi chunk văn bản."""
    source: str = Field(default="", description="Tên file hoặc URL nguồn")
    topic: str = Field(
        default="",
        description="Chủ đề, ví dụ: địa chất, lịch sử, du lịch, truyền thuyết"
    )
    language: str = Field(default="vi", description="Ngôn ngữ: vi hoặc en")
    chunk_index: int = Field(default=0, description="Thứ tự chunk trong tài liệu gốc")
    total_chunks: int = Field(default=1, description="Tổng số chunk của tài liệu gốc")


# ── Collection: chat_history ──────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """Một tin nhắn trong cuộc hội thoại."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=utc_now)
    sources: list[str] = Field(
        default_factory=list,
        description="doc_id các chunk đã dùng để tạo câu trả lời (chỉ có ở role=assistant)"
    )


class ChatSession(BaseModel):
    """
    Một phiên hội thoại, lưu toàn bộ lịch sử messages.
    Mỗi document trong collection 'chat_history' là một session.
    """
    session_id: str = Field(description="UUID của phiên hội thoại")
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    model_config = {"populate_by_name": True}


# ── API Schemas (request / response) ─────────────────────────────────────────

class ChatRequest(BaseModel):
    """Request body gửi từ client tới POST /chat."""
    session_id: Optional[str] = Field(
        default=None,
        description="Nếu None, server sẽ tạo session mới"
    )
    message: str = Field(
        min_length=1,
        max_length=2000,
        description="Câu hỏi của người dùng"
    )


class SourceReference(BaseModel):
    """Tham chiếu nguồn trả về cùng câu trả lời."""
    doc_id: str
    content_preview: str = Field(description="~150 ký tự đầu của chunk")
    topic: str
    source: str


class ChatResponse(BaseModel):
    """Response trả về client sau mỗi lượt hội thoại."""
    session_id: str
    answer: str
    sources: list[SourceReference] = Field(default_factory=list)
    response_time_ms: Optional[float] = None
