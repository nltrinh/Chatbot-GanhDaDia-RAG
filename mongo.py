"""
Kết nối MongoDB và khởi tạo collections cho hệ thống chatbot Gành Đá Đĩa.
"""

from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, OperationFailure
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class MongoDB:
    client: MongoClient = None
    db: Database = None

    def connect(self):
        """Kết nối tới MongoDB local."""
        try:
            self.client = MongoClient(
                settings.MONGO_URI,
                serverSelectionTimeoutMS=5000,
            )
            # Kiểm tra kết nối
            self.client.admin.command("ping")
            self.db = self.client[settings.MONGO_DB_NAME]
            logger.info(f"✅ Kết nối MongoDB thành công: {settings.MONGO_URI}")
            self._ensure_indexes()
        except ConnectionFailure as e:
            logger.error(f"❌ Không thể kết nối MongoDB: {e}")
            raise

    def disconnect(self):
        """Đóng kết nối MongoDB."""
        if self.client:
            self.client.close()
            logger.info("🔌 Đã đóng kết nối MongoDB.")

    def _ensure_indexes(self):
        """Tạo indexes cần thiết nếu chưa có."""
        try:
            # Index cho documents collection
            docs_col = self.get_documents_collection()
            docs_col.create_index([("doc_id", ASCENDING)], unique=True)
            docs_col.create_index([("source", ASCENDING)])
            docs_col.create_index([("topic", ASCENDING)])

            # Index cho chat_history collection
            history_col = self.get_chat_history_collection()
            history_col.create_index([("session_id", ASCENDING)])
            history_col.create_index([("created_at", ASCENDING)])

            logger.info("📑 Indexes đã được tạo/kiểm tra.")
        except OperationFailure as e:
            logger.warning(f"⚠️ Không thể tạo index: {e}")

    # ---------- Helpers ----------

    def get_documents_collection(self) -> Collection:
        """Collection lưu chunks văn bản + vector embedding."""
        return self.db[settings.COLLECTION_DOCUMENTS]

    def get_chat_history_collection(self) -> Collection:
        """Collection lưu lịch sử hội thoại."""
        return self.db[settings.COLLECTION_CHAT_HISTORY]


# Singleton instance
mongodb = MongoDB()


# ---------- Dependency cho FastAPI ----------

def get_db() -> MongoDB:
    return mongodb
