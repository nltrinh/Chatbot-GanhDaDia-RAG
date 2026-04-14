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
> **"Chào Agent, bạn hãy đóng vai là một kỹ sư Backend & AI Expert. Tôi vừa mới kết nối vào một máy chủ mới. Nhiệm vụ của bạn là đọc hiểu file `AGENT_AUTO_DEPLOY.md` này để nắm bắt kiến trúc hiện tại (Qwen2.5 14B, MongoDB 8, BGE-M3) và thực thi tất cả các bước để đưa hệ thống Chatbot RAG Gành Đá Đĩa lên trạng thái chạy ổn định (Ready to Demo). Hãy tự động kiểm tra GPU, cài đặt dependencies, cấu hình ENV và khởi động server với 4 workers. Tôi chỉ việc ngồi xem bạn thực hiện."**
> ---

---

## 📋 TỔNG QUAN KIẾN TRÚC HIỆN TẠI
- **Hệ điều hành:** Linux/Ubuntu (Tối ưu cho Vast.ai, Runpod, EC2).
- **Mô hình LLM:** `qwen2.5` - Linh hoạt theo VRAM (Dùng `1.5b` cho máy yếu, `7b` cho trung bình, `14b` cho máy mạnh).
- **Mô hình Embedding:** `bge-m3` (Vector 1024D đa ngôn ngữ).
- **Database:** **MongoDB 8 Local** (Chế độ Replica Set `rs0` để hỗ trợ Vector Search).
- **Tính năng cao cấp:** Hybrid Search (RRF), Multi-session (Đa phiên chat), Markdown Rendering, Persistence (Lưu lịch sử chat).

---

## 🛠 CÁC BƯỚC TRIỂN KHAI CHI TIẾT

### BƯỚC 0: Kiểm tra phần cứng (Quan trọng)
Agent hãy thực hiện `nvidia-smi` để kiểm tra dung lượng VRAM:
- **VRAM < 8GB:** Hãy đổi model LLM trong `.env` và lệnh pull thành `qwen2.5:1.5b`.
- **VRAM 8GB - 12GB:** Dùng `qwen2.5:7b`.
- **VRAM > 12GB:** Dùng `qwen2.5:14b` (Cấu hình mặc định hiện tại).
- **Nếu máy chỉ có CPU:** Dùng `llama3.2:1b` để đảm bảo tốc độ phản hồi tối thiểu.

### BƯỚC 1: Cấu hình Hệ thống & MongoDB 8
Mục tiêu: Đảm bảo MongoDB 8 đang chạy với Replica Set `rs0`.
```bash
# Khởi động MongoDB (nếu chưa chạy)
mkdir -p ~/data/db
mongod --port 27017 --dbpath ~/data/db --replSet rs0 --fork --logpath ~/data/mongod.log

# Khởi tạo Replica Set (chỉ làm 1 lần đầu trên máy mới)
mongosh --eval 'rs.initiate()'
```

### BƯỚC 2: Cài đặt Ollama & Tải mô hình AI
Agent cần đảm bảo Ollama đã được cài đặt và nhận diện GPU:
1. Cài đặt Ollama (nếu chưa có):
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. Khởi chạy và tải Models:
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
2. Tạo file `.env` (Agent tự động tạo nội dung này):
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
2. Khởi động Web Server (Production mode):
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
Agent thực hiện lệnh Health Check:
```bash
curl -s http://localhost:8000/health | jq .
```
Nếu `mongodb: "ok"` và `total_chunks > 0`, bạn đã hoàn thành nhiệm vụ!

---
> **Lưu ý cho Agent:** Luôn ưu tiên dùng `run_command` để thực thi và `view_file` để kiểm tra trạng thái file. Chúc bạn triển khai thành công!
