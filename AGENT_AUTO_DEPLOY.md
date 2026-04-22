# 🤖 Hướng Dẫn Tự Động Hóa Cho AI Agent (Agent Auto-Deploy Prompt)

> **🗣 LƯU Ý DÀNH CHO BẠN (CÁCH SỬ DỤNG FILE NÀY):**
> Mỗi khi thuê một máy chủ hoàn toàn mới (VD trên Vast.ai/VPS Trắng), bạn chỉ cần gõ 1 lệnh duy nhất này vào terminal để kéo bộ mã nguồn về máy:
> 
> ```bash
> # Sử dụng Token (PAT) nếu repo Private hoặc clone thông thường:
> git clone https://github.com/nltrinh/Chatbot-GanhDaDia-RAG.git && cd Chatbot-GanhDaDia-RAG
> ```
> 
> Tiếp theo, hãy mở IDE (VSCode / Cursor) có tích hợp AI Agent, mở file này lên và copy/paste dòng thoại dưới đây cho AI của bạn:
> ---
> **"Chào Agent, bạn hãy đóng vai là một kỹ sư Backend & AI Expert. Tôi vừa mới kết nối vào một máy chủ mới. Nhiệm vụ của bạn là đọc hiểu file `AGENT_AUTO_DEPLOY.md` này để nắm bắt kiến trúc hiện tại ĐÃ ĐƯỢC CỐ ĐỊNH (Qwen2.5 14B, MongoDB 8, BGE-M3) và thực thi tất cả các bước để đưa hệ thống Chatbot RAG Gành Đá Đĩa lên trạng thái chạy ổn định (Ready to Demo). Hãy cài đặt dependencies, chạy hệ thống và test kết quả phản hồi,cấu hình ENV và khởi động server với 4 workers. Lưu ý: Luôn sử dụng mô hình Qwen2.5:14b bất kể cấu hình máy như thế nào."**
> ---

---

## 📋 TỔNG QUAN KIẾN TRÚC CỐ ĐỊNH (BEST PERFORMANCE)
- **Hệ điều hành:** Linux/Ubuntu (Tối ưu cho Vast.ai, Runpod, EC2).
- **Mô hình LLM (Cố định):** `qwen2.5:14b` (Mô hình tốt nhất cho Tiếng Việt hiện nay).
- **Mô hình Embedding (Cố định):** `bge-m3` (Vector 1024D đa ngôn ngữ mạnh nhất).
- **Database:** **MongoDB 8 Local** (Chế độ Replica Set `rs0` để hỗ trợ Vector Search).
- **Tính năng cao cấp:** Hybrid Search (RRF), Multi-session (Đa phiên chat), Markdown Rendering, Persistence (Lưu lịch sử chat).

---

## 🛠 CÁC BƯỚC TRIỂN KHAI CHI TIẾT

### BƯỚC 1: Cấu hình Hệ thống & MongoDB 8
```bash
# Khởi động MongoDB (nếu chưa chạy)
mkdir -p ~/data/db
mongod --port 27017 --dbpath ~/data/db --replSet rs0 --fork --logpath ~/data/mongod.log

# Khởi tạo Replica Set
mongosh --eval 'rs.initiate()'
```

### BƯỚC 2: Cài đặt Ollama & Tải mô hình AI Cố định
1. Cài đặt Ollama:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. Tải chính xác cặp Models "khủng":
   ```bash
   ollama pull bge-m3
   ollama pull qwen2.5:14b
   ```

### BƯỚC 3: Thiết lập Python Backend
1. Cài đặt Python env:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Tạo file `.env`:
   ```env
   # MongoDB
   MONGO_URI=mongodb://localhost:27017/?replicaSet=rs0
   MONGO_DB_NAME=ganh_da_dia_bot
   COLLECTION_DOCUMENTS=documents
   COLLECTION_CHAT_HISTORY=chat_history
   COLLECTION_UPLOADED_FILES=uploaded_files
   COLLECTION_VECTOR_CACHE=vector_search_cache

   # Ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_LLM_MODEL=qwen2.5:14b
   OLLAMA_EMBED_MODEL=bge-m3
   OLLAMA_NUM_PREDICT=1000
   ```

### BƯỚC 4: Khởi chạy và Nạp dữ liệu mẫu
1. Tạo index tìm kiếm văn bản:
   ```bash
   mongosh ganh_da_dia_bot --eval 'db.documents.createIndex({content: "text"})'
   ```
2. Khởi động Web Server:
   ```bash
   source venv/bin/activate
   nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 > server.log 2>&1 &
   ```
3. Nạp dữ liệu từ thư mục mẫu:
   ```bash
   curl -X POST -F "file=@sample_data/ganh_da_dia_text.txt" http://localhost:8000/admin/upload
   curl -X POST -F "file=@sample_data/ganh_da_dia.pdf" http://localhost:8000/admin/upload
   ```

### BƯỚC 5: Kiểm tra cuối cùng
```bash
curl -s http://localhost:8000/health | jq .
```

---
> **Lưu ý cho Agent:** Không thay đổi mô hình LLM. Sử dụng đúng Qwen2.5:14b như yêu cầu.
