"""
Retriever: nhận câu hỏi → embed → tìm kiếm $vectorSearch trong MongoDB
→ trả về top-k chunks liên quan nhất.
"""

import logging
import requests
import numpy as np
from pymongo import MongoClient

from app.core.config import settings

logger = logging.getLogger(__name__)

MONGO_URI = settings.MONGO_URI
DB_NAME = settings.MONGO_DB_NAME
COLLECTION_DOCS = settings.COLLECTION_DOCUMENTS
OLLAMA_URL = settings.OLLAMA_BASE_URL
EMBED_MODEL = settings.OLLAMA_EMBED_MODEL
TOP_K = settings.TOP_K_RESULTS


def embed_query(text: str) -> list[float]:
    """Embed câu hỏi thành vector."""
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


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Tìm kiếm top-k chunks liên quan nhất bằng $vectorSearch.
    Trả về list các dict: {doc_id, content, topic, source, score}
    """
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        db = client[DB_NAME]
        collection = db[COLLECTION_DOCS]

        query_vector = embed_query(query)

        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": top_k * 10,
                    "limit": top_k,
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "doc_id": 1,
                    "content": 1,
                    "metadata": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        results = list(collection.aggregate(pipeline))
        logger.info(f"🔍 Tìm được {len(results)} chunks cho query: '{query[:50]}...'")
        return results

    finally:
        client.close()


if __name__ == "__main__":
    # Test nhanh
    logging.basicConfig(level=logging.INFO)
    results = retrieve("Gành Đá Đĩa ở đâu?")
    for r in results:
        print(f"\n[{r['metadata']['topic']}] score={r['score']:.4f}")
        print(r["content"][:150])
