"""
Script khởi tạo MongoDB Vector Search Index cho collection 'documents'.

Chạy một lần duy nhất trước khi ingest dữ liệu:
    python -m app.db.init_db

Yêu cầu:
  - MongoDB >= 7.0 (hỗ trợ $vectorSearch với Atlas Search local)
  - Hoặc dùng mongod với --setParameter enableTestCommands=1 (dev)

Lưu ý: MongoDB Community edition KHÔNG hỗ trợ $vectorSearch.
Nếu đang dùng Community, xem phần FALLBACK bên dưới — dùng cosine
similarity thủ công hoặc chuyển sang MongoDB Atlas (free tier).
"""

import sys
import logging
from pymongo import MongoClient
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


VECTOR_INDEX_DEFINITION = {
    "name": "vector_index",
    "type": "vectorSearch",
    "definition": {
        "fields": [
            {
                "type": "vector",
                "path": "embedding",
                "numDimensions": settings.EMBEDDING_DIM,   # 768 cho nomic-embed-text
                "similarity": "cosine",
            },
            {
                # Filter theo topic khi search
                "type": "filter",
                "path": "metadata.topic",
            },
            {
                # Filter theo ngôn ngữ
                "type": "filter",
                "path": "metadata.language",
            },
        ]
    },
}


def create_vector_index(client: MongoClient) -> bool:
    """
    Tạo Atlas Vector Search index trên collection documents.
    Trả về True nếu thành công, False nếu không hỗ trợ (Community edition).
    """
    db = client[settings.MONGO_DB_NAME]
    collection = db[settings.COLLECTION_DOCUMENTS]

    # Kiểm tra index đã tồn tại chưa
    existing = list(collection.list_search_indexes())
    for idx in existing:
        if idx.get("name") == "vector_index":
            logger.info("✅ Vector index 'vector_index' đã tồn tại, bỏ qua.")
            return True

    try:
        collection.create_search_index(VECTOR_INDEX_DEFINITION)
        logger.info("✅ Đã tạo Vector Search index thành công.")
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if "not supported" in error_msg or "enterprise" in error_msg or "atlas" in error_msg:
            logger.warning(
                "⚠️  MongoDB Community không hỗ trợ $vectorSearch.\n"
                "   → Fallback: dùng cosine similarity thủ công trong retriever.py\n"
                "   → Hoặc nâng lên MongoDB Atlas (free tier tại mongodb.com/atlas)"
            )
            return False
        else:
            logger.error(f"❌ Lỗi tạo index: {e}")
            raise


def create_regular_indexes(client: MongoClient):
    """Tạo các regular index (hoạt động trên mọi phiên bản MongoDB)."""
    db = client[settings.MONGO_DB_NAME]

    # documents collection
    docs = db[settings.COLLECTION_DOCUMENTS]
    docs.create_index("doc_id", unique=True)
    docs.create_index("metadata.topic")
    docs.create_index("metadata.source")
    logger.info("✅ Regular indexes cho 'documents' đã được tạo.")

    # chat_history collection
    history = db[settings.COLLECTION_CHAT_HISTORY]
    history.create_index("session_id", unique=True)
    history.create_index("created_at")
    logger.info("✅ Regular indexes cho 'chat_history' đã được tạo.")


def main():
    logger.info(f"🔗 Kết nối tới {settings.MONGO_URI} ...")
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)

    try:
        client.admin.command("ping")
        logger.info("✅ MongoDB kết nối thành công.")
    except Exception as e:
        logger.error(f"❌ Không thể kết nối MongoDB: {e}")
        sys.exit(1)

    # Tạo regular indexes (luôn chạy)
    create_regular_indexes(client)

    # Thử tạo vector index (chỉ hoạt động trên Atlas / Enterprise)
    vector_supported = create_vector_index(client)

    if not vector_supported:
        logger.info(
            "\n📌 Hệ thống sẽ dùng chế độ FALLBACK:\n"
            "   - Embedding vẫn được lưu vào MongoDB\n"
            "   - Khi search: load embeddings ra Python, tính cosine similarity thủ công\n"
            "   - Phù hợp cho dev/demo; chuyển Atlas khi production nếu cần tốc độ\n"
        )

    client.close()
    logger.info("🏁 Khởi tạo database hoàn tất.")


if __name__ == "__main__":
    main()
