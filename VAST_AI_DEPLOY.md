# 🌩️ Hướng dẫn Triển khai Gành Đá Đĩa RAG lên Vast.ai (Kèm AI Agent Debugging)

Tài liệu này cung cấp các bước chính xác nhất để thiết lập và chạy hệ thống trên máy ảo GPU của Vast.ai. Đồng thời, tài liệu hướng dẫn cách mang **Antigravity AI Agent** lên máy chủ để tự động bắt lỗi và thiết lập thay bạn.

---

## 1. Thuê Máy và Cấu Hình Đầu Vào (Vast.ai)
1. Đăng nhập vào [Vast.ai Console](https://console.vast.ai).
2. Xây dựng config máy (Edit Image & Config):
   - **Docker Image**: Chọn `nvidia/cuda:12.1.1-devel-ubuntu22.04` (Hoặc OS mặc định của Vast.ai Cuda/Docker).
   - **Storage**: Tối thiểu 30GB Disk space (Docker Image và các model của llama cũng khá nặng).
   - **Port Forwarding (QUAN TRỌNG)**: Chọn dấu `+` để Add Port Mapping. Thêm cổng `8000` (FastAPI) để có thể xem web được từ xa.
3. Nhấn **Rent** để thuê GPU (vd: RTX 3090 / 4090).
4. Ở tab **Instances**, đợi trạng thái máy thành `running` màu xanh. Sau đó lấy các thông tin SSH: IP, Port (ví dụ: `ssh root@12.34.56.78 -p 12345`).

---

## 2. Kết nối VSCode và Antigravity Agent vào Vast.ai
Đây là bước "hack" siêu mạnh! Để tôi (Agent Antigravity) có thể tự động đọc file và khắc phục lỗi giúp bạn trên mội trường Vast.ai, bạn làm như sau:

1. Mở phần mềm Visual Studio Code (VSCode) trên máy tính cá nhân của bạn hiện tại.
2. Tải Extension **Remote - SSH** của Microsoft.
3. Nhập lệnh SSH mà Vast.ai cung cấp vào VSCode (Nhấp vào icon `><` dưới cùng bên trái màn hình > `Connect to Host` > Điền IP/Port).
4. Sau khi kết nối thành công, tải mã nguồn (Git Clone) thư mục dự án lên máy tính đó, sau đó chọn **File -> Open Folder...** và mở thư mục vừa tải.
5. Lúc này, **Antigravity Extension** trên VSCode của bạn sẽ khởi chạy ngay tại máy chủ Linux Vast.ai.
	- 💡 **Từ bây giờ**, nếu trong lúc gõ lệnh bạn gặp bất kỳ lỗi màu đỏ nào trên Terminal, hoặc Server tự thoát (crash), bạn chỉ cần bật khung chat tôi lên và yêu cầu: *"Kiểm tra log server và sửa lỗi giúp tôi"*, hệ thống sẽ tự dùng tool khắc phục.

---

## 3. Cài Đặt Các Module Cơ Bản
Trên VSCode Terminal kết nối với Vast.ai, hãy chạy chuỗi lệnh sau:

### 3.1 Cài đặt môi trường Python & Git
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git nano
```

### 3.2 Khởi động Background Services (MongoDB)
Hệ thống sử dụng Docker Compose để chuẩn bị DB. Vast OS thường có sẵn docker, bạn chỉ cần gõ:
```bash
# Sẽ mất vài phút nhổ Docker image MongoDB Atlas Local
docker-compose up -d
```

### 3.3 Chuẩn bị AI Engine (Ollama) cho GPU
Ollama phải được cài riêng để nhận tài nguyên card Nvidia:
```bash
# Cài tool Ollama chính thức:
curl -fsSL https://ollama.com/install.sh | sh

# Tải trước 2 model thiết yếu:
ollama pull llama3.2:1b
ollama pull nomic-embed-text
```

---

## 4. Xây dựng & Kích hoạt Python Server
Tạo một không gian riêng ảo (virtual environment) cho ứng dụng tránh lỗi đụng chạm System Python:

```bash
# Tạo môi trường base_env
python3 -m venv base_env
source base_env/bin/activate

# Cài đặt toàn bộ thư viện (langchain, fastapi, ...)
pip install -r requirements.txt
```

Sao chép `.env` (Nếu chưa có, hãy tạo từ example):
```bash
cp env.example .env
```

Tại đây, bạn không cần đổi `MONGO_URI` hay các địa chỉ nội bộ khác vì Docker và Ollama đều chạy tại localhost của máy tính Vast.ai.

---

## 5. Chạy Server Thử Nghiệm Tích Hợp
Kích hoạt uvicorn:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Nếu Console in ra `Application startup complete.` và không có màu đỏ, xin chúc mừng!

**Khởi dụng từ ngoài mạng Internet:**
- Vào lại bảng lưới (Instances) trên trang web Vast.ai.
- Tìm máy chủ của bạn hiển thị. Tìm cột **Port Forwarding**, nó sẽ hiện các dòng ánh xạ (ví dụ: `8000/tcp -> 44102`).
- Hãy nhập trên Chrome: `http://<IP-vast>:<Cổng-Ánh-Xạ>/admin/ui` (VD: `http://192.168.1.1:44102/admin/ui`).
- Tiện ích đồ họa tải lên dữ liệu sẽ hiện ra để bạn tải các file PDF lên thử nghiệm tốc độ sinh thực sự của phần cứng GPU khổng lồ!

## 🆘 Quy Trình Debug Tự Động (Agentic Healing)
Nếu tại bất kì bước nào ở trên thất bại (Thiếu Cuda, lỗi xung đột pip, model bị ngắt kết nối):
1. Đừng làm gì cả.
2. Bật panel Antigravity góc trái.
3. Ping cú pháp: *"Tôi đang lỗi khi chạy lệnh cài X, hãy quét qua tiến trình và sửa"* -> Agent sẽ tự động dò log, viết file vá (patch) lại đường dẫn ngay trên ổ cứng Vast.ai của bạn.
