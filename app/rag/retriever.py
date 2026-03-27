"""
Retriever: nhận câu hỏi → embed → tìm kiếm $vectorSearch trong MongoDB
→ lọc theo score threshold → trả về top-k chunks liên quan nhất.
"""

import logging
import requests
import numpy as np
from pymongo import MongoClient

logger = logging.getLogger(__name__)

MONGO_URI   = "mongodb://localhost:27018/?directConnection=true"
DB_NAME     = "ganh_da_dia_bot"
COL_DOCS    = "documents"
OLLAMA_URL  = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
TOP_K       = 5
SCORE_MIN   = 0.75   # bỏ qua chunks có độ liên quan thấp hơn ngưỡng này


def embed_query(text: str) -> list[float]:
    """Embed câu hỏi thành vector đơn vị."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    arr  = np.array(resp.json()["embedding"], dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


def retrieve(
    query: str,
    top_k: int = TOP_K,
    topic_filter: str = None,
    exclude_sources: list[str] = None,
) -> list[dict]:
    """
    Tìm kiếm top-k chunks liên quan nhất bằng $vectorSearch.

    Args:
        query           : câu hỏi của người dùng
        top_k           : số chunks trả về (mặc định 5)
        topic_filter    : lọc theo topic cụ thể (ví dụ: "du lịch")
        exclude_sources : danh sách tên file muốn loại ra

    Returns:
        list[{doc_id, content, metadata, score}]
    """
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        collection = client[DB_NAME][COL_DOCS]

        # Embed câu hỏi
        query_vector = embed_query(query)

        # Xây dựng $vectorSearch pipeline
        vector_search_stage = {
            "$vectorSearch": {
                "index":        "vector_index",
                "path":         "embedding",
                "queryVector":  query_vector,
                "numCandidates": top_k * 15,   # lấy nhiều candidate để lọc
                "limit":         top_k * 3,    # lấy dư để sau đó filter score
            }
        }

        # Thêm filter theo topic nếu có
        if topic_filter:
            vector_search_stage["$vectorSearch"]["filter"] = {
                "metadata.topic": {"$eq": topic_filter}
            }

        pipeline = [
            vector_search_stage,
            {
                "$project": {
                    "_id":      0,
                    "doc_id":   1,
                    "content":  1,
                    "metadata": 1,
                    "score":    {"$meta": "vectorSearchScore"},
                }
            },
            # Lọc score thấp
            {"$match": {"score": {"$gte": SCORE_MIN}}},
            # Giới hạn kết quả cuối
            {"$limit": top_k},
        ]

        results = list(collection.aggregate(pipeline))

        # Loại bỏ sources không mong muốn (tùy chọn)
        if exclude_sources:
            results = [
                r for r in results
                if r.get("metadata", {}).get("file_name") not in exclude_sources
            ]

        # Log kết quả
        if results:
            logger.info(
                f"🔍 '{query[:40]}' → {len(results)} chunks "
                f"(score: {results[0]['score']:.3f}–{results[-1]['score']:.3f})"
            )
        else:
            logger.warning(f"⚠️ Không tìm thấy chunk nào đủ liên quan cho: '{query[:40]}'")

        return results

    finally:
        client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = retrieve("lưu ý khi tham quan gành đá đĩa")
    for r in results:
        src   = r["metadata"].get("file_name", "?")
        topic = r["metadata"].get("topic", "?")
        print(f"\n[{topic}] [{src}] score={r['score']:.4f}")
        print(r["content"][:200])