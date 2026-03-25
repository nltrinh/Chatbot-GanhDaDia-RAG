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

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "llama3.2"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"

    # RAG
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K_RESULTS: int = 5
    EMBEDDING_DIM: int = 768          # nomic-embed-text output dimension

    # API
    APP_TITLE: str = "Chatbot Gành Đá Đĩa"
    APP_VERSION: str = "1.0.0"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
