"""
RAG Chain: nhận câu hỏi + lịch sử hội thoại
→ retrieve context → gọi Ollama LLM → trả về câu trả lời + sources.

Dùng /api/generate với Llama 3 chat template chính thức.
Tương thích Ollama 0.18.0 trở lên.
"""

import logging
import requests
from app.rag.retriever import retrieve
from app.core.config import settings

logger = logging.getLogger(__name__)

OLLAMA_URL = settings.OLLAMA_BASE_URL
LLM_MODEL = settings.OLLAMA_LLM_MODEL

SYSTEM_PROMPT = """Bạn là trợ lý ảo hỗ trợ thông tin về Gành Đá Đĩa, Phú Yên.
Bạn sẽ trả lời câu hỏi dựa trên ngữ cảnh (CONTEXT) được cung cấp dưới đây.
- Trả lời bằng tiếng Việt, thân thiện và chính xác.
- Nếu ngữ cảnh có thông tin, hãy tổng hợp nội dung quan trọng nhất.
- Nếu ngữ cảnh mang tính liệt kê (file PDF/docx upload lên), hãy tóm tắt ý chính của tài liệu đó.
- Nếu không tìm thấy thông tin phù hợp trong ngữ cảnh, hãy nói "Tôi chưa có thông tin chi tiết về vấn đề này trong tài liệu hiện có."
- Luôn chỉ sử dụng thông tin trong CONTEXT.

CONTEXT:
{context}
"""


def build_context(chunks: list[dict]) -> str:
    """Xây dựng chuỗi ngữ cảnh từ list các chunks."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        # Ưu tiên topic, nếu không lấy source/file_name
        source = meta.get("source") or meta.get("file_name", "Unknown")
        topic = meta.get("topic", "")
        header = f"[{i}] ({source})" + (f" - {topic}" if topic else "")
        content = chunk.get("content", "").strip()
        parts.append(f"{header}: {content}")
    return "\n\n".join(parts)


def build_prompt(query: str, context: str, history: list[dict]) -> str:
    """
    Xây dựng prompt theo đúng Llama 3 chat template.
    Format này giúp llama3.2 hiểu và tuân theo instruction chính xác hơn.
    """
    parts = []
    parts.append("<|begin_of_text|>")

    # System
    parts.append(
        f"<|start_header_id|>system<|end_header_id|>\n"
        f"{SYSTEM_PROMPT.format(context=context)}<|eot_id|>"
    )

    # Lịch sử hội thoại (tối đa 4 lượt gần nhất)
    for msg in history[-4:]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role in ("user", "assistant"):
            parts.append(
                f"<|start_header_id|>{role}<|end_header_id|>\n"
                f"{content}<|eot_id|>"
            )

    # Câu hỏi hiện tại kèm context
    user_content = (
        f"Dựa vào thông tin sau đây để trả lời câu hỏi:\n\n"
        f"{context}\n\n"
        f"Câu hỏi: {query}"
    )
    parts.append(
        f"<|start_header_id|>user<|end_header_id|>\n"
        f"{user_content}<|eot_id|>"
    )

    # Kết thúc — model sẽ sinh tiếp từ đây
    parts.append("<|start_header_id|>assistant<|end_header_id|>")

    return "".join(parts)


def chat(query: str, history: list[dict] = None) -> dict:
    """
    Hàm chính của RAG chain.

    Args:
        query: Câu hỏi của người dùng
        history: Lịch sử hội thoại [{role, content}, ...]

    Returns:
        {answer, sources, chunks_used}
    """
    if history is None:
        history = []

    # 1. Retrieve
    chunks = retrieve(query)
    context = build_context(chunks)

    # 2. Build prompt theo Llama 3 chat template
    prompt = build_prompt(query, context, history)

    # 3. Gọi Ollama /api/generate
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 300,
                    "stop": ["<|eot_id|>", "<|end_of_text|>"],
                },
            },
            timeout=1200,
        )
        resp.raise_for_status()
        answer = resp.json()["response"].strip()

    except requests.exceptions.Timeout:
        answer = "Xin lỗi, hệ thống đang xử lý chậm. Vui lòng thử lại."
    except Exception as e:
        logger.error(f"Lỗi gọi Ollama: {e}")
        answer = "Xin lỗi, có lỗi xảy ra. Vui lòng thử lại."

    # 4. Build sources
    sources = [
        {
            "doc_id": c.get("doc_id", ""),
            "content_preview": c.get("content", "")[:150],
            "topic": c.get("metadata", {}).get("topic", ""),
            "source": c.get("metadata", {}).get("source", ""),
            "score": round(c.get("score", 0), 4),
        }
        for c in chunks
    ]

    return {
        "answer": answer,
        "sources": sources,
        "chunks_used": len(chunks),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = chat("quy định gành đá đĩa")
    print("\n=== CÂU TRẢ LỜI ===")
    print(result["answer"])
    print(f"\n=== NGUỒN ({result['chunks_used']} chunks) ===")
    for s in result["sources"]:
        print(f"- [{s['topic']}] score={s['score']}: {s['content_preview'][:80]}...")