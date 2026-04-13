# 🚀 Hướng Dẫn Triển Khai Tự Động Hóa 100% lên Vast.ai

Chào bạn, tôi đã chuẩn bị mọi thứ để bạn có thể thuê máy và chạy dự án chỉ với vài thao tác chuột. Toàn bộ mã nguồn mới nhất tối ưu cho GPU đã được tôi đẩy lên GitHub.

---

## Bước 1: Chuẩn bị SSH Key (Bảo mật & Tiện lợi)
Việc này giúp bạn không cần gõ mật khẩu mỗi khi vào máy chủ.

1.  **Kiểm tra/Tạo Key trên máy bạn:**
    - Mở CMD hoặc Terminal trên máy tính cá nhân.
    - Gõ: `ssh-keygen -t ed25519 -C "your_email@example.com"` (Nhấn Enter liên tục).
2.  **Lấy chuỗi mã Public:**
    - Gõ: `cat ~/.ssh/id_ed25519.pub` (Hoặc mở file đó bằng Notepad).
    - Copy toàn bộ nội dung (bắt đầu bằng `ssh-ed25519...`).
3.  **Dán vào Vast.ai:**
    - Truy cập [Vast.ai Account Keys](https://cloud.vast.ai/account/).
    - Dán vào ô **SSH Public Key** và chọn **Add Key**.

---

## Bước 2: Thiết lập Template Tự Động (Chỉ làm 1 lần)
Bạn sẽ tạo một "Khuôn mẫu" để lần sau cứ thuê máy là nó tự chạy.

1.  Tại Dashboard Vast.ai, chọn **Templates** -> **NVIDIA CUDA**.
2.  Nhấn nút **Edit** (Cây bút).
3.  **Trong ô Docker Options:** Dán thêm `-p 8000:8000` vào đầu dòng.
4.  **Trong ô On-start Script:** Xóa sạch và dán đoạn mã bên dưới vào:

```bash
#!/bin/bash
# Tải script tự động hóa từ Github của bạn
curl -fsSL https://raw.githubusercontent.com/nltrinh/Chatbot-GanhDaDia-RAG/main/vast_setup.sh | bash
```

5.  **Disk Space:** Chỉnh thành **50 GB**.
6.  Nhấn **SELECT & SAVE**.

---

## Bước 3: Thuê Máy & Kiểm tra Kết quả
1.  Quay lại trang **Search**, tìm máy GPU bạn muốn (VD: RTX 3060, 3090, 4090...).
2.  Bấm **RENT**.
3.  Chuyển sang tab **Instances**. Bạn sẽ thấy máy đang ở trạng thái `Creating` -> `Running`.
4.  **Chờ khoảng 5 phút** để script tự động cài đặt MongoDB, Ollama và tải Model AI (vì các model này nặng tổng cộng ~4GB).
5.  **Truy cập Web:**
    - Nhìn vào bảng điều khiển máy, tìm cột **Port Forwarding**.
    - Tìm dòng: `8000/tcp -> [Số cổng 5 chữ số]` (Ví dụ: `34567`).
    - Mở trình duyệt và truy cập: `http://[IP-MÁY]:[Số-Cổng]/admin/ui`
    - *(Ví dụ: http://123.456.7.8:34567/admin/ui)*

---

## 🛠️ Cách Dùng Agent Antigravity Để Sửa Lỗi (Nếu có)
Nếu bạn vào web không được hoặc muốn xem tiến trình đang chạy đến đâu:

1.  Bấm nút **Connect trên Vast.ai** để lấy lệnh SSH (VD: `ssh root@12.3.4.5 -p 12345`).
2.  Mở VSCode trên máy bạn -> Nhấn `F1` -> `Remote-SSH: Connect to Host`.
3.  Dán lệnh SSH vào. VSCode sẽ mở ra môi trường Server Vast.ai.
4.  **Sửa lỗi:** Chỉ cần chat với tôi (Antigravity) ngay trong VSCode đó. Tôi có thể tự gõ `tmux a -t rag_session` để xem log lỗi và sửa code trực tiếp trên Server giúp bạn.

**CẢNH BÁO:** Vast.ai sẽ sạc tiền theo giờ. Hãy bấm **DESTROY** máy khi bạn đã thử nghiệm xong để tránh lãng phí tiền.
