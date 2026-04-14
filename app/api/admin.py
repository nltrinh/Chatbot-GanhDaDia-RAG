"""
Admin API — Quản lý tài liệu cho hệ thống RAG.

Endpoints:
  POST   /admin/upload          — upload file (txt, pdf, docx)
  GET    /admin/files           — danh sách file đã upload
  GET    /admin/files/{id}      — chi tiết + tiến độ xử lý
  DELETE /admin/files/{id}      — xóa file + toàn bộ chunks
  GET    /admin/stats           — thống kê tổng quan
  POST   /admin/search          — vector search trực tiếp (có cache)
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from pymongo import MongoClient

from app.core.config import settings
from app.rag.pipeline import ingest_file, search_vectors

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

ALLOWED_TYPES = {".txt", ".pdf", ".docx"}
MAX_FILE_MB = 20


# ── MongoDB helper ─────────────────────────────────────────────────────────────


def get_db():
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    return client[settings.MONGO_DB_NAME]


# ── Background pipeline ────────────────────────────────────────────────────────


def _process_file_background(
    file_id: str,
    file_name: str,
    file_type: str,
    content: bytes,
):
    """Chạy pipeline nạp tài liệu ở background. Cập nhật tiến độ vào DB."""
    db = get_db()
    col = db[settings.COLLECTION_UPLOADED_FILES]

    def set_status(status: str, pct: int = 0, extra: dict = None):
        update = {
            "status": status,
            "progress_pct": pct,
            "updated_at": datetime.now(timezone.utc),
        }
        if extra:
            update.update(extra)
        col.update_one({"file_id": file_id}, {"$set": update})

    try:
        set_status("processing", 10)

        result = ingest_file(
            content=content,
            file_name=file_name,
            file_type=file_type,
            file_id=file_id,
        )

        col.update_one(
            {"file_id": file_id},
            {
                "$set": {
                    "status": "ready",
                    "progress_pct": 100,
                    "chunks_total": result["chunks_total"],
                    "chunks_saved": result["chunks_saved"],
                    "chunks_skipped": result["skipped"],
                    "completed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    except Exception as e:
        logger.error(f"❌ Lỗi xử lý {file_name}: {e}")
        set_status("failed", 0, {"error_msg": str(e)})


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload file .txt/.pdf/.docx — tự động chunking, embedding, lưu DB."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ: {suffix}. Chỉ chấp nhận: {', '.join(ALLOWED_TYPES)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail=f"File quá lớn. Tối đa {MAX_FILE_MB}MB"
        )

    db = get_db()
    file_id = str(uuid.uuid4())

    db[settings.COLLECTION_UPLOADED_FILES].insert_one(
        {
            "file_id": file_id,
            "file_name": file.filename,
            "file_type": suffix.lstrip("."),
            "file_size": len(content),
            "status": "queued",
            "progress_pct": 0,
            "chunks_total": 0,
            "chunks_saved": 0,
            "chunks_skipped": 0,
            "error_msg": None,
            "uploaded_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "completed_at": None,
        }
    )

    background_tasks.add_task(
        _process_file_background,
        file_id=file_id,
        file_name=file.filename,
        file_type=suffix,
        content=content,
    )

    return {
        "file_id": file_id,
        "file_name": file.filename,
        "status": "queued",
        "message": "Đang xử lý. Theo dõi tiến độ tại GET /admin/files/{file_id}",
    }


@router.get("/files")
def list_files():
    """Danh sách tất cả file đã upload."""
    db = get_db()
    files = list(
        db[settings.COLLECTION_UPLOADED_FILES]
        .find(
            {},
            {
                "_id": 0,
                "file_id": 1,
                "file_name": 1,
                "file_type": 1,
                "file_size": 1,
                "status": 1,
                "progress_pct": 1,
                "chunks_total": 1,
                "chunks_saved": 1,
                "uploaded_at": 1,
                "completed_at": 1,
            },
        )
        .sort("uploaded_at", -1)
    )
    return {"files": files, "total": len(files)}


@router.get("/files/{file_id}")
def get_file_status(file_id: str):
    """Chi tiết và tiến độ xử lý của một file."""
    db = get_db()
    record = db[settings.COLLECTION_UPLOADED_FILES].find_one(
        {"file_id": file_id}, {"_id": 0}
    )
    if not record:
        raise HTTPException(status_code=404, detail="File không tồn tại")
    return record


@router.delete("/files/{file_id}")
def delete_file(file_id: str):
    """Xóa file và toàn bộ chunks liên quan trong DB."""
    db = get_db()
    record = db[settings.COLLECTION_UPLOADED_FILES].find_one({"file_id": file_id})
    if not record:
        raise HTTPException(status_code=404, detail="File không tồn tại")

    result = db[settings.COLLECTION_DOCUMENTS].delete_many(
        {"metadata.file_id": file_id}
    )
    db[settings.COLLECTION_UPLOADED_FILES].delete_one({"file_id": file_id})

    return {
        "message": f"Đã xóa '{record['file_name']}'",
        "chunks_deleted": result.deleted_count,
    }


@router.get("/stats")
def get_stats():
    """Thống kê tổng quan hệ thống."""
    db = get_db()
    total_chunks = db[settings.COLLECTION_DOCUMENTS].count_documents({})
    total_files = db[settings.COLLECTION_UPLOADED_FILES].count_documents({})
    ready = db[settings.COLLECTION_UPLOADED_FILES].count_documents({"status": "ready"})
    processing = db[settings.COLLECTION_UPLOADED_FILES].count_documents(
        {"status": {"$in": ["queued", "processing"]}}
    )
    failed = db[settings.COLLECTION_UPLOADED_FILES].count_documents(
        {"status": "failed"}
    )
    cached_queries = db[settings.COLLECTION_VECTOR_CACHE].count_documents({})

    by_type = {
        r["_id"]: r["count"]
        for r in db[settings.COLLECTION_UPLOADED_FILES].aggregate(
            [{"$group": {"_id": "$file_type", "count": {"$sum": 1}}}]
        )
    }

    return {
        "total_chunks": total_chunks,
        "total_files": total_files,
        "ready_files": ready,
        "processing_files": processing,
        "failed_files": failed,
        "cached_queries": cached_queries,
        "by_type": by_type,
    }


# ── Vector Search Endpoint ─────────────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.delete("/cache/clear")
def clear_vector_cache():
    """Xóa toàn bộ cache tìm kiếm vector."""
    db = get_db()
    result = db[settings.COLLECTION_VECTOR_CACHE].delete_many({})
    return {
        "message": "Đã xóa toàn bộ cache tìm kiếm",
        "deleted_count": result.deleted_count,
    }


@router.post("/search")
def vector_search(req: SearchRequest):
    """
    Vector search trực tiếp — hiển thị kết quả + query vector + cache status.
    Dùng để demo và kiểm tra chất lượng retrieval.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query không được để trống")

    result = search_vectors(req.query, top_k=req.top_k)

    return {
        "query": req.query,
        "cached": result["cached"],
        "search_time_ms": result["search_time_ms"],
        "query_vector_preview": result["query_vector"][:10],  # 10 dims đầu
        "query_vector_dim": len(result["query_vector"]),
        "results": result["results"],
        "total": len(result["results"]),
    }
