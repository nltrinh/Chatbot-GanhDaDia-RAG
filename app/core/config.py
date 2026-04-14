"""
Cấu hình toàn bộ ứng dụng từ file .env
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MongoDB
    MONGO_URI: str = "mongodb://localhost:27018/?directConnection=true"
    MONGO_DB_NAME: str = "ganh_da_dia_bot"
    COLLECTION_DOCUMENTS: str = "documents"
    COLLECTION_CHAT_HISTORY: str = "chat_history"
    COLLECTION_UPLOADED_FILES: str = "uploaded_files"
    COLLECTION_VECTOR_CACHE: str = "vector_search_cache"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "llama3.2:1b"  # Nhỏ hơn, nhanh hơn 3x cho demo
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"

    # MongoDB Vector Search Index name
    VECTOR_INDEX_NAME: str = "vector_index"

    # RAG
    CHUNK_SIZE: int = 400
    CHUNK_OVERLAP: int = 50
    TOP_K_RESULTS: int = 3
    EMBEDDING_DIM: int = 768  # nomic-embed-text output dimension
    OLLAMA_NUM_PREDICT: int = 150  # Giới hạn token để tăng tốc sinh kết quả

    # API
    APP_TITLE: str = "Chatbot Gành Đá Đĩa"
    APP_VERSION: str = "2.0.0"
    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
