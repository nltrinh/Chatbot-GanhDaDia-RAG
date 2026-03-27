"""
Admin API — quản lý tài liệu cho hệ thống RAG.

Endpoints:
  POST   /admin/upload        — upload file (txt, pdf, docx)
  GET    /admin/files         — danh sách file đã upload
  GET    /admin/files/{id}    — chi tiết + tiến độ xử lý
  DELETE /admin/files/{id}    — xóa file + toàn bộ chunks
  GET    /admin/stats         — thống kê tổng quan
"""

import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import requests
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pymongo import MongoClient

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

MONGO_URI        = "mongodb://localhost:27018/?directConnection=true"
DB_NAME          = "ganh_da_dia_bot"
COL_DOCS         = "documents"
COL_FILES        = "uploaded_files"
OLLAMA_URL       = "http://localhost:11434"
EMBED_MODEL      = "nomic-embed-text"
EMBEDDING_DIM    = 768
CHUNK_SIZE       = 500
CHUNK_OVERLAP    = 50
ALLOWED_TYPES    = {".txt", ".pdf", ".docx"}
MAX_FILE_MB      = 20

router = APIRouter(prefix="/admin", tags=["admin"])


# ── MongoDB helpers ───────────────────────────────────────────────────────────

def get_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client[DB_NAME]


# ── File processing pipeline ──────────────────────────────────────────────────

def hash_file(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_text_from_bytes(content: bytes, file_type: str, file_name: str) -> list[dict]:
    """
    Trích xuất text từ file bytes.
    Trả về list[{text, page_num}]
    """
    pages = []

    if file_type == ".txt":
        text = content.decode("utf-8", errors="ignore")
        pages.append({"text": text, "page_num": 1})

    elif file_type == ".pdf":
        try:
            import pypdf
            import io
            reader = pypdf.PdfReader(io.BytesIO(content))
            for i, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append({"text": text, "page_num": i})
        except Exception as e:
            raise ValueError(f"Không đọc được PDF: {e}")

    elif file_type == ".docx":
        try:
            import docx
            import io
            doc = docx.Document(io.BytesIO(content))
            full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            pages.append({"text": full_text, "page_num": 1})
        except Exception as e:
            raise ValueError(f"Không đọc được DOCX: {e}")

    return pages


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Tách text thành chunks, ưu tiên cắt tại dấu câu."""
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            for sep in [".\n", ". ", "\n\n", "\n", " "]:
                pos = text.rfind(sep, start + chunk_size // 2, end)
                if pos != -1:
                    end = pos + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap

    return chunks


def embed_text(text: str) -> list[float]:
    """Embed text thành vector bằng Ollama."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    arr = np.array(resp.json()["embedding"], dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


def process_file_background(
    file_id: str,
    file_name: str,
    file_type: str,
    file_hash: str,
    content: bytes,
):
    """
    Background task: xử lý file và lưu vào MongoDB.
    Cập nhật tiến độ realtime vào collection uploaded_files.
    """
    db = get_db()
    col_files = db[COL_FILES]
    col_docs = db[COL_DOCS]

    def update_status(status: str, progress: int = 0, processed: int = 0,
                      total: int = 0, error: str = None):
        update = {
            "status": status,
            "progress_pct": progress,
            "chunks_processed": processed,
            "total_chunks": total,
            "updated_at": datetime.now(timezone.utc),
        }
        if error:
            update["error_msg"] = error
        col_files.update_one({"file_id": file_id}, {"$set": update})

    try:
        # Bước 1: Load text
        update_status("loading", progress=5)
        pages = load_text_from_bytes(content, file_type, file_name)
        if not pages:
            raise ValueError("File không có nội dung văn bản")

        # Bước 2: Split thành chunks
        update_status("splitting", progress=15)
        all_chunks = []
        for page in pages:
            chunks = split_text(page["text"])
            for idx, chunk in enumerate(chunks):
                all_chunks.append({
                    "text": chunk,
                    "page_num": page["page_num"],
                    "chunk_index": idx,
                })

        total = len(all_chunks)
        if total == 0:
            raise ValueError("Không tách được chunk nào từ file")

        update_status("embedding", progress=20, total=total)

        # Bước 3: Embed + lưu từng chunk
        for i, chunk_info in enumerate(all_chunks):
            doc_id = f"{file_id}_chunk_{i}"

            # Embed
            embedding = embed_text(chunk_info["text"])

            # Lưu vào MongoDB
            doc = {
                "doc_id": doc_id,
                "content": chunk_info["text"],
                "embedding": embedding,
                "metadata": {
                    "file_id": file_id,
                    "source": file_name,
                    "file_name": file_name,
                    "file_type": file_type.lstrip("."),
                    "file_hash": file_hash,
                    "page_num": chunk_info["page_num"],
                    "chunk_index": chunk_info["chunk_index"],
                    "total_chunks": total,
                    "language": "vi",
                    "topic": "",        # admin có thể gán sau
                },
                "created_at": datetime.now(timezone.utc),
            }

            try:
                col_docs.insert_one(doc)
            except Exception:
                pass  # duplicate key — bỏ qua

            # Cập nhật tiến độ mỗi 5 chunks hoặc chunk cuối
            processed = i + 1
            if processed % 5 == 0 or processed == total:
                pct = 20 + int((processed / total) * 75)
                update_status("embedding", progress=pct,
                              processed=processed, total=total)

        # Hoàn tất
        col_files.update_one(
            {"file_id": file_id},
            {"$set": {
                "status": "ready",
                "progress_pct": 100,
                "chunks_processed": total,
                "total_chunks": total,
                "completed_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        logger.info(f"✅ Xử lý xong file {file_name} — {total} chunks")

    except Exception as e:
        logger.error(f"❌ Lỗi xử lý file {file_name}: {e}")
        update_status("failed", error=str(e))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload file txt/pdf/docx, xử lý bất đồng bộ."""
    # Kiểm tra định dạng
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ: {suffix}. Chỉ chấp nhận: {', '.join(ALLOWED_TYPES)}"
        )

    # Đọc nội dung
    content = await file.read()

    # Kiểm tra kích thước
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File quá lớn. Tối đa {MAX_FILE_MB}MB"
        )

    # Kiểm tra file trùng lặp
    file_hash = hash_file(content)
    db = get_db()
    existing = db[COL_FILES].find_one({"file_hash": file_hash, "status": "ready"})
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"File này đã được upload trước đó: '{existing['file_name']}'"
        )

    # Tạo record trong uploaded_files
    file_id = str(uuid.uuid4())
    file_record = {
        "file_id": file_id,
        "file_name": file.filename,
        "file_type": suffix.lstrip("."),
        "file_hash": file_hash,
        "file_size": len(content),
        "status": "queued",
        "progress_pct": 0,
        "chunks_processed": 0,
        "total_chunks": 0,
        "error_msg": None,
        "uploaded_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "completed_at": None,
    }
    db[COL_FILES].insert_one(file_record)

    # Chạy pipeline bất đồng bộ
    background_tasks.add_task(
        process_file_background,
        file_id=file_id,
        file_name=file.filename,
        file_type=suffix,
        file_hash=file_hash,
        content=content,
    )

    return {
        "file_id": file_id,
        "file_name": file.filename,
        "status": "queued",
        "message": "File đang được xử lý. Dùng GET /admin/files/{file_id} để theo dõi tiến độ.",
    }


@router.get("/files")
def list_files():
    """Danh sách tất cả file đã upload."""
    db = get_db()
    files = list(db[COL_FILES].find(
        {},
        {"_id": 0, "file_id": 1, "file_name": 1, "file_type": 1,
         "file_size": 1, "status": 1, "progress_pct": 1,
         "total_chunks": 1, "uploaded_at": 1, "completed_at": 1}
    ).sort("uploaded_at", -1))

    return {"files": files, "total": len(files)}


@router.get("/files/{file_id}")
def get_file_status(file_id: str):
    """Chi tiết và tiến độ xử lý của một file."""
    db = get_db()
    record = db[COL_FILES].find_one({"file_id": file_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="File không tồn tại")
    return record


@router.delete("/files/{file_id}")
def delete_file(file_id: str):
    """Xóa file và toàn bộ chunks liên quan."""
    db = get_db()

    # Kiểm tra file tồn tại
    record = db[COL_FILES].find_one({"file_id": file_id})
    if not record:
        raise HTTPException(status_code=404, detail="File không tồn tại")

    # Xóa chunks
    result = db[COL_DOCS].delete_many({"metadata.file_id": file_id})
    chunks_deleted = result.deleted_count

    # Xóa record file
    db[COL_FILES].delete_one({"file_id": file_id})

    return {
        "message": f"Đã xóa '{record['file_name']}'",
        "chunks_deleted": chunks_deleted,
    }


@router.get("/stats")
def get_stats():
    """Thống kê tổng quan hệ thống."""
    db = get_db()

    total_docs = db[COL_DOCS].count_documents({})
    total_files = db[COL_FILES].count_documents({})
    ready_files = db[COL_FILES].count_documents({"status": "ready"})
    processing = db[COL_FILES].count_documents({"status": {"$in": ["queued", "loading", "splitting", "embedding"]}})
    failed = db[COL_FILES].count_documents({"status": "failed"})

    # Thống kê theo loại file
    pipeline = [{"$group": {"_id": "$file_type", "count": {"$sum": 1}}}]
    by_type = {r["_id"]: r["count"] for r in db[COL_FILES].aggregate(pipeline)}

    return {
        "total_chunks": total_docs,
        "total_files": total_files,
        "ready_files": ready_files,
        "processing_files": processing,
        "failed_files": failed,
        "by_type": by_type,
    }