<br />
<div align="center">
  <img src="https://raw.githubusercontent.com/nltrinh/Chatbot-GanhDaDia-RAG/main/app/static/logo.png" alt="Logo" width="120" onerror="this.src='https://cdn-icons-png.flaticon.com/512/4712/4712038.png'">
  <h1 align="center">🪨 Chatbot Gành Đá Đĩa RAG</h1>
  <p align="center">
    <strong>Hệ thống Trí tuệ Nhân tạo thông minh, giải đáp thông tin về Quần thể danh thắng Quốc gia Đặc biệt Gành Đá Đĩa (Phú Yên)</strong>
    <br />
    <br />
    <a href="#-tính-năng-cốt-lõi">Tính năng</a>
    ·
    <a href="#-kiến-trúc-hệ-thống">Kiến trúc</a>
    ·
    <a href="#-triển-khai-nhanh-quick-start">Triển Khai Mẫu</a>
  </p>
  
  [![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white)](https://python.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
  [![MongoDB](https://img.shields.io/badge/MongoDB-8.0-47A248.svg?logo=mongodb&logoColor=white)](https://mongodb.com)
  [![Ollama](https://img.shields.io/badge/AI_Engine-Ollama-white.svg?logo=ollama&logoColor=black)](https://ollama.com)
  [![LangChain](https://img.shields.io/badge/Framework-LangChain_0.3-orange.svg)](https://langchain.com)
</div>

## 🌟 Tính Năng Cốt Lõi

- **100% Khép Kín (Local-First):** Hệ thống được xây dựng để không phụ thuộc vào bất kỳ API nào bên ngoài (như OpenAI, Anthropic,...). Đảm bảo bảo vệ dữ liệu nội quyền (`Privacy-first`) và zero-cost execution (Không mất tiền inference).
- **RAG Nâng Cao (Hybrid Search):** Thay vì chỉ match text thông thường, dự án cài đặt cơ chế lai ghép **Reciprocal Rank Fusion (RRF)**. Kết hợp sức mạnh của **Native MQL Vector Dot-Product** trên không gian 768 chiều và **BM25 Keyword Search** của hạt nhân MongoDB 8.
- **LLM Thời Gian Thực (Chuyên Trị Tiếng Việt):** Trang bị mô hình não **Qwen-2.5 14B** (phiên bản LLM mã nguồn mở đỉnh cao nhất cho văn bản Tiếng Việt hiện nay) hoạt động cực mượt nhờ nền tảng nội suy Ollama, phù hợp cho GPU từ 16GB VRAM.
- **Automated AI Deployment:** Đóng gói thông minh dưới dạng *Agent Config* - một AI Agent có thể đọc mã và tự động setup Cloud Server từ máy trắng sang Trạng thái Ready để Demo.

## 🏗️ Kiến Trúc Khung

Dự án bao gồm 4 thành phần trụ cột:
1. **Application Server (FastAPI):** Orchestrator điều phối API, Web UI, tiếp nhận Files và xử lý các luồng Streaming cho Client.
2. **Knowledge Base (MongoDB 8 local):** Trung tâm cơ sở lưu trữ dữ liệu văn bản linh hoạt và hệ Vector Search phi cấu trúc.
3. **Inference Neural Engine (Ollama):** Trạm phát API nội bộ cấp quyền truy xuất hai model:
   - `bge-m3`: Tokenizer đa ngôn ngữ mạnh nhất để chuyển hóa chữ Hán/Việt/Anh sang toạ độ không gian.
   - `qwen2.5:14b`: Core LLM vượt trội cho Tiếng Việt để giao tiếp & phân tích tài liệu.
4. **LangChain 0.3 Framework:** Công nghệ mắc nối lõi bằng chuẩn `LCEL` (LangChain Expression Language).

## 🚀 Triển Khai Nhanh (Quick Start)

Dự án này đã loại bỏ hoàn toàn Docker để tối ưu tối đa hiệu năng GPU/CPU thô của máy chủ. Nó có thể chạy trực tiếp trên Server Ubuntu trắng (như Vast.ai, Runpod, AWS EC2,...).

### Phương Pháp 1: Dùng Môi Giới Trí Tuệ Nhân Tạo (Khuyên dùng)
Nếu bạn đang sử dụng VSCode (hoặc Cursor) có tích hợp AI Agent trên server, chỉ việc mở Terminal tại file `AGENT_AUTO_DEPLOY.md` và ra lệnh: 
> *"Agent, hãy thực thi toàn bộ script trong AGENT_AUTO_DEPLOY.md."*

Cỗ máy AI sẽ tự động thay bạn cài cắm toàn bộ Mongo, Ollama, Python Dependencies và khởi động Web Server thành công!

### Phương Pháp 2: Chạy Bằng Tay (Manual Deploy)

**Bước 1: Cấu hình Cơ Sở Dữ Liệu (MongoDB 8)**
Khởi động cấu trúc Replica Set (bắt buộc đối với Native Vector):
```bash
mongod --port 27017 --dbpath ~/data/db --replSet rs0 --fork --logpath ~/data/mongod.log
mongosh --eval 'rs.initiate()'
```

**Bước 2: Cấu hình Trí tuệ (Ollama)**
```bash
ollama pull bge-m3
ollama pull qwen2.5:14b
```

**Bước 3: Biên Dịch Backend**
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
mongosh ganh_da_dia_bot --eval 'db.documents.createIndex({content: "text"})'
```

**Bước 4: Bật Trạm Phát và Tải Tri Thức Ban Đầu**
```bash
# Start Server FastAPI Backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Mở Terminal khác để nhúng File Tri thức (Tự Tách Chunk & Cấy Vector)
curl -X POST -F "file=@sample_data/ganh_da_dia_text.txt" http://localhost:8000/admin/upload
```

🌍 Mọi thứ đã hoàn tất, mời bạn truy cập:
- **Giao diện trải nghiệm Chat:** `http://localhost:8000/`
- **Trung tâm quản trị (Swagger API):** `http://localhost:8000/docs`

---
> Xin trân trọng giới thiệu, cống hiến cho công cuộc số hoá di sản Gành Đá Đĩa Việt Nam.
> **Developed by: nltrinh**
