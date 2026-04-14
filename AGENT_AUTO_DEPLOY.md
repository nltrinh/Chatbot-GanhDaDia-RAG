# 🤖 Hướng Dẫn Tự Động Hóa Cho AI Agent (Agent Auto-Deploy Prompt)

> **🗣 LƯU Ý DÀNH CHO BẠN (CÁCH SỬ DỤNG FILE NÀY):**
> Mỗi khi thuê một máy chủ hoàn toàn mới (VD trên Vast.ai/VPS Trắng), bạn chỉ cần gõ 1 lệnh duy nhất này vào terminal để kéo bộ mã nguồn về máy:
> 
> ```bash
> # Nếu Repo là Công khai (Public):
> git clone https://github.com/nltrinh/Chatbot-GanhDaDia-RAG.git && cd Chatbot-GanhDaDia-RAG
> 
> # Nếu Repo là Riêng tư (Private), hãy sử dụng Token (PAT), LƯU Ý không lưu lệnh chứa Token vào script cố định để tránh rò rỉ:
> git clone https://<YOUR_GITHUB_TOKEN>@github.com/nltrinh/Chatbot-GanhDaDia-RAG.git && cd Chatbot-GanhDaDia-RAG
> ```
> 
> Tiếp theo, hãy mở IDE (VSCode / Cursor) có tích hợp AI Agent, mở file này lên và copy/paste dòng thoại dưới đây cho AI của bạn:
> ---
> **"Chào Agent, bạn hãy đóng vai là một kỹ sư AI/Backend. Tôi vừa mới thuê một máy chủ ảo mới (Linux/Ubuntu). Nhiệm vụ của bạn là đọc hiểu toàn bộ file `AGENT_AUTO_DEPLOY.md` này và thực thi tuần tự, cẩn thận tất cả các bước bên dưới để hệ thống Chatbot RAG khởi chạy thành công 100%. Mọi thông tin nhạy cảm đã được loại bỏ khỏi repo, cứ tự động thay đổi biến môi trường nếu cần thiết. Hãy sử dụng các công cụ bạn có (run_command, view_file) để hoàn thành mọi việc, tôi chỉ việc ngồi xem bạn thao tác."**
> ---

---

## 📋 THỨ TỰ THỰC THI DÀNH CHO AGENT
*(Lưu ý cho Agent: Hãy dùng tool `run_command` chạy từng lệnh bash một cách chắc chắn. Chờ tiến trình trước hoàn tất rồi mới làm tiến trình sau).*

### BƯỚC 1: Cài đặt & Cấu hình MongoDB 8 Replica Set (Bắt buộc cho Vector/Hybrid Search)
1. Thêm key và repo của MongoDB 8.0:
   ```bash
   curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
   echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-8.0.list
   apt-get update && apt-get install -y mongodb-org
   ```
2. Tạo thư mục chứa dữ liệu và cấu hình chạy ẩn (fork) với chế độ Replica Set:
   ```bash
   mkdir -p /root/data/db
   mongod --port 27017 --dbpath /root/data/db --replSet rs0 --bind_ip 0.0.0.0 --fork --logpath /root/data/mongod.log
   ```
3. Khởi tạo Replica Set (Sleep khoảng 3 giây sau lệnh trên và chạy lệnh này):
   ```bash
   mongosh --eval 'rs.initiate()'
   ```

### BƯỚC 2: Cài đặt Ollama & Tải AI Models
1. Cài đặt Ollama Platform (nếu OS chưa có):
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. Background chạy Ollama nếu chưa chạy (Hoặc kiểm tra bằng `ollama list`). Sau đó kích hoạt tải mô hình AI chạy Local:
   ```bash
   ollama pull nomic-embed-text
   ollama pull llama3.2:1b
   ```

### BƯỚC 3: Cài đặt Môi trường Python Backend
1. Tạo môi trường ảo và cài thư viện:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Sử dụng tool `replace_file_content` hoặc shell bash để cập nhật file `.env` nội dung cốt lõi sau:
   ```env
   # MongoDB
   MONGO_URI=mongodb://localhost:27017/?replicaSet=rs0
   MONGO_DB_NAME=ganh_da_dia_bot
   COLLECTION_DOCUMENTS=documents
   COLLECTION_CHAT_HISTORY=chat_history

   # Ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_LLM_MODEL=llama3.2:1b
   OLLAMA_EMBED_MODEL=nomic-embed-text
   ```

### BƯỚC 4: Khởi chạy API Server & Nạp Dữ Liệu
1. Chạy Backend FastAPI chạy ngầm bằng tham số (RunPersistent=True của run_command) hoặc tmux:
   ```bash
   source venv/bin/activate
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. **Tạo Text Index dùng cho kỹ thuật Hybrid Search:** (Vì local MongoDB 8 cần Full-text Index cho Keyword Fallback bên cạnh chấm Dot-Product Vector)
   ```bash
   mongosh ganh_da_dia_bot --eval 'db.documents.createIndex({content: "text"})'
   ```
3. Nạp tài liệu (Tải file text/pdf thông qua API nội bộ để hệ thống tự chunking và embedding lên MongoDB):
   ```bash
   curl -X POST -F "file=@ganh_da_dia_text.txt" http://localhost:8000/admin/upload
   curl -X POST -F "file=@ganh_da_dia.pdf" http://localhost:8000/admin/upload
   ```

### BƯỚC 5: Kiểm Tra Lại & Báo Cáo
Cuối cùng, Agent hãy gọi thử lệnh sau để kiểm tra trạng thái Hybrid Search & LLM Generator của mô hình Langchain có xuất kết quả tốt không:
```bash
curl -s -X POST -H "Content-Type: application/json" -d '{"message": "Gành đá đĩa ở đâu vậy?"}' http://localhost:8000/chat
```
Nếu mọi thứ hoạt động thành công (JSON có chứa answer và câu trả lời được sinh ra), Agent hãy nhắn lại báo cho tôi (User) biết là hoàn tất mọi thứ để tôi tự lên trình duyệt vào thẳng Web UI nhé!
