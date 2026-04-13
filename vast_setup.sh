#!/bin/bash
# ==============================================================================
# BASH SCRIPT: AUTOMATED RAG SETUP FOR VAST.AI (DOCKER BASED)
# Tối ưu cho môi trường Vast.ai - Không cần gõ lệnh thủ công
# ==============================================================================

echo "🚀 Bắt đầu tự động hóa thiết lập RAG..."

# 1. Cài đặt các gói cơ bản
apt-get update
apt-get install -y curl git python3-venv python3-pip docker-compose tmux nano

# 2. Tải mã nguồn dự án
cd /workspace
if [ -d "Chatbot-GanhDaDia-RAG" ]; then
    rm -rf Chatbot-GanhDaDia-RAG
fi
git clone https://github.com/nltrinh/Chatbot-GanhDaDia-RAG.git
cd Chatbot-GanhDaDia-RAG

# 3. Kích hoạt MongoDB Atlas Local qua Docker
# Chú ý: Vast.ai thường có sẵn Docker. 
echo "🍃 Khởi động MongoDB (Docker)..."
docker-compose up -d

# 4. Cài đặt Ollama AI Engine (GPU acceleration)
echo "🧠 Cài đặt Ollama..."
curl -fsSL https://ollama.com/install.sh | sh
# Chạy Ollama ngầm để kéo model
ollama serve > /dev/null 2>&1 &
sleep 10
ollama pull llama3.2:1b
ollama pull nomic-embed-text

# 5. Setup môi trường Python
echo "📂 Cấu hình Python venv..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Tạo file .env dựa trên example
cp env.example .env

# 6. Khởi chạy Server trong Session ngầm (TMUX)
# Cổng 72299 thường được mở sẵn trên các Template Vast.ai hoặc map qua 8000
echo "🛰️ Khởi chạy API Server..."
tmux new-session -d -s rag_session "source /workspace/Chatbot-GanhDaDia-RAG/venv/bin/activate && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo "----------------------------------------------------------------"
echo "✅ HOÀN TẤT TỰ ĐỘNG HÓA!"
echo "Server đang chạy ngầm trên cổng 8000."
echo "Hãy kiểm tra Port Forwarding trên Vast.ai Dashboard."
echo "----------------------------------------------------------------"
