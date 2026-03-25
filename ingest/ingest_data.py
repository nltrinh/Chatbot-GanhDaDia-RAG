"""
Script ingest dữ liệu về Gành Đá Đĩa vào MongoDB với Vector Search index.

Luồng xử lý:
  JSON file → chunk văn bản → embed bằng Ollama → lưu MongoDB → tạo vector index

Chạy:
    python ingest/ingest_data.py
    python ingest/ingest_data.py --file data/ganh_da_dia_sample.json
    python ingest/ingest_data.py --reset   # Xóa sạch và ingest lại
"""

import argparse
import json
import logging
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import requests
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

# Thêm thư mục gốc vào sys.path để import được app.core.config
sys.path.append(str(Path(__file__).parent.parent))
from app.core.config import settings

# ── Cấu hình ──────────────────────────────────────────────────────────────────
MONGO_URI = settings.MONGO_URI
DB_NAME = settings.MONGO_DB_NAME
COLLECTION_DOCS = settings.COLLECTION_DOCUMENTS
COLLECTION_HISTORY = settings.COLLECTION_CHAT_HISTORY

OLLAMA_URL = settings.OLLAMA_BASE_URL
EMBED_MODEL = settings.OLLAMA_EMBED_MODEL
EMBEDDING_DIM = settings.EMBEDDING_DIM

CHUNK_SIZE = settings.CHUNK_SIZE
CHUNK_OVERLAP = settings.CHUNK_OVERLAP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_ollama() -> bool:
    """Kiểm tra Ollama đang chạy và model embed có sẵn."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        available = any(EMBED_MODEL in m for m in models)
        if not available:
            logger.warning(
                f"⚠️  Model '{EMBED_MODEL}' chưa được pull.\n"
                f"   Chạy: ollama pull {EMBED_MODEL}"
            )
        return available
    except Exception:
        logger.error(
            "❌ Ollama chưa chạy. Khởi động Ollama trước:\n"
            "   Windows: mở app Ollama hoặc chạy 'ollama serve'"
        )
        return False


def embed_text(text: str) -> list[float]:
    """Gọi Ollama API để lấy vector embedding."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    embedding = resp.json()["embedding"]
    # Normalize về unit vector (tốt hơn cho cosine similarity)
    arr = np.array(embedding, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Chia văn bản thành các chunk theo ký tự.
    Cố gắng cắt tại dấu câu để chunk tự nhiên hơn.
    """
    if len(text) <= chunk_size:
        return [text.strip()]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        if end < len(text):
            # Tìm dấu câu gần nhất để cắt tự nhiên
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


def create_vector_search_index(collection) -> bool:
    """
    Tạo Atlas Vector Search index trên collection documents.
    Hoạt động với mongodb/mongodb-atlas-local Docker image.
    """
    index_name = "vector_index"

    # Kiểm tra đã có index chưa
    try:
        existing = list(collection.list_search_indexes())
        for idx in existing:
            if idx.get("name") == index_name:
                logger.info(f"✅ Vector Search index '{index_name}' đã tồn tại.")
                return True
    except Exception:
        pass

    index_definition = {
        "name": index_name,
        "type": "vectorSearch",
        "definition": {
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": EMBEDDING_DIM,
                    "similarity": "cosine",
                },
                {
                    "type": "filter",
                    "path": "metadata.topic",
                },
                {
                    "type": "filter",
                    "path": "metadata.language",
                },
            ]
        },
    }

    try:
        collection.create_search_index(index_definition)
        logger.info(f"✅ Đã tạo Vector Search index '{index_name}'.")

        # Chờ index ready (atlas-local cần vài giây)
        logger.info("⏳ Chờ index build xong...")
        for i in range(30):
            time.sleep(2)
            indexes = list(collection.list_search_indexes())
            for idx in indexes:
                if idx.get("name") == index_name:
                    status = idx.get("status", "")
                    if status == "READY":
                        logger.info("✅ Vector Search index sẵn sàng!")
                        return True
                    logger.info(f"   Trạng thái: {status} ({i*2}s)...")
                    break

        logger.warning("⚠️  Index chưa READY sau 60s, tiếp tục ingest...")
        return True

    except Exception as e:
        logger.error(f"❌ Không thể tạo vector index: {e}")
        logger.info("   → Fallback: cosine similarity thủ công sẽ được dùng khi query.")
        return False


# ── Main ingest ───────────────────────────────────────────────────────────────

def ingest_file(filepath: str, client: MongoClient, reset: bool = False):
    db = client[DB_NAME]
    collection = db[COLLECTION_DOCS]

    if reset:
        deleted = collection.delete_many({})
        logger.info(f"🗑️  Đã xóa {deleted.deleted_count} documents cũ.")

    # Đọc dữ liệu
    path = Path(filepath)
    if not path.exists():
        logger.error(f"❌ File không tồn tại: {filepath}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        raw_data = json.load(f)

    logger.info(f"📂 Đọc {len(raw_data)} documents từ {path.name}")

    total_chunks = 0
    total_embedded = 0
    skipped = 0

    for item_idx, item in enumerate(raw_data):
        content = item.get("content", "").strip()
        source = item.get("source", "unknown")
        topic = item.get("topic", "")
        language = item.get("language", "vi")

        if not content:
            logger.warning(f"⚠️  Document #{item_idx} không có nội dung, bỏ qua.")
            continue

        # Chunk văn bản
        chunks = chunk_text(content)
        total_chunks += len(chunks)

        for chunk_idx, chunk_text_content in enumerate(chunks):
            doc_id = f"{path.stem}_{item_idx:03d}_chunk_{chunk_idx}"

            # Bỏ qua nếu đã tồn tại (idempotent)
            if collection.find_one({"doc_id": doc_id}):
                skipped += 1
                continue

            # Embed
            try:
                embedding = embed_text(chunk_text_content)
            except Exception as e:
                logger.error(f"❌ Lỗi embed chunk {doc_id}: {e}")
                continue

            # Lưu vào MongoDB
            doc = {
                "doc_id": doc_id,
                "content": chunk_text_content,
                "embedding": embedding,
                "metadata": {
                    "source": source,
                    "topic": topic,
                    "language": language,
                    "chunk_index": chunk_idx,
                    "total_chunks": len(chunks),
                },
            }

            try:
                collection.insert_one(doc)
                total_embedded += 1
                logger.info(
                    f"  ✅ [{total_embedded:03d}] {doc_id} "
                    f"| topic={topic} | {len(chunk_text_content)} ký tự"
                )
            except DuplicateKeyError:
                skipped += 1

    logger.info(
        f"\n{'─'*50}\n"
        f"📊 Kết quả ingest:\n"
        f"   - Tổng chunks: {total_chunks}\n"
        f"   - Đã embed & lưu: {total_embedded}\n"
        f"   - Bỏ qua (đã có): {skipped}\n"
        f"   - Collection: {DB_NAME}.{COLLECTION_DOCS}\n"
        f"{'─'*50}"
    )

    return total_embedded > 0


def setup_regular_indexes(client: MongoClient):
    """Tạo các regular index (không cần Atlas)."""
    db = client[DB_NAME]

    # documents
    col_docs = db[COLLECTION_DOCS]
    col_docs.create_index("doc_id", unique=True)
    col_docs.create_index("metadata.topic")
    col_docs.create_index("metadata.source")

    # chat_history
    col_history = db[COLLECTION_HISTORY]
    col_history.create_index("session_id", unique=True, sparse=True)
    col_history.create_index("created_at")

    logger.info("✅ Regular indexes đã được tạo.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest dữ liệu Gành Đá Đĩa vào MongoDB")
    parser.add_argument(
        "--file",
        default="data/ganh_da_dia_sample.json",
        help="Đường dẫn file JSON dữ liệu (default: data/ganh_da_dia_sample.json)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Xóa toàn bộ dữ liệu cũ trước khi ingest lại",
    )
    args = parser.parse_args()

    logger.info("🚀 Bắt đầu ingest dữ liệu Gành Đá Đĩa\n")

    # 1. Kiểm tra Ollama
    logger.info("1️⃣  Kiểm tra Ollama...")
    if not check_ollama():
        sys.exit(1)
    logger.info(f"   ✅ Ollama OK — model: {EMBED_MODEL}")

    # 2. Kết nối MongoDB
    logger.info("\n2️⃣  Kết nối MongoDB...")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        logger.info(f"   ✅ MongoDB OK — {DB_NAME}")
    except Exception as e:
        logger.error(f"   ❌ Không thể kết nối MongoDB: {e}")
        sys.exit(1)

    # 3. Tạo regular indexes
    logger.info("\n3️⃣  Tạo indexes...")
    setup_regular_indexes(client)

    # 4. Ingest dữ liệu
    logger.info(f"\n4️⃣  Ingest file: {args.file}")
    success = ingest_file(args.file, client, reset=args.reset)

    if not success:
        logger.error("❌ Ingest thất bại hoặc không có dữ liệu mới.")
        client.close()
        sys.exit(1)

    # 5. Tạo Vector Search index
    logger.info("\n5️⃣  Tạo Vector Search index...")
    db = client[DB_NAME]
    create_vector_search_index(db[COLLECTION_DOCS])

    client.close()
    logger.info("\n🎉 Ingest hoàn tất! Sẵn sàng cho bước RAG chain.")


if __name__ == "__main__":
    main()
