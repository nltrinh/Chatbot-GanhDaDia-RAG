import streamlit as st
import google.generativeai as genai
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# --- 1. CẤU HÌNH TRANG WEB ---
st.set_page_config(
    page_title="Chatbot Gành Đá Đĩa",
    page_icon="🌊",
    layout="centered"
)

st.title("🌊 Hướng dẫn viên ảo - Gành Đá Đĩa")
st.caption("🚀 Sản phẩm thực tập AI - Hỗ trợ du lịch Phú Yên")

# --- 2. CẤU HÌNH API ---
# QUAN TRỌNG: Dán API Key của bạn vào giữa dấu ngoặc kép bên dưới
MY_API_KEY = "HAY_DIEN_API_KEY_CUA_BAN_VAO_DAY"

# Cấu hình Google Gemini
try:
    genai.configure(api_key=MY_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=MY_API_KEY)
except Exception as e:
    st.error(f"Lỗi cấu hình API: {e}")

# --- 3. HÀM NẠP DỮ LIỆU (Chạy 1 lần thôi cho nhanh) ---
@st.cache_resource
def load_data():
    try:
        # Load vector database từ ổ cứng
        db = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
        return db
    except Exception as e:
        return None

# Gọi hàm nạp dữ liệu
db = load_data()

# Kiểm tra nếu chưa có dữ liệu thì báo lỗi
if db is None:
    st.error("⚠️ CHƯA TÌM THẤY DỮ LIỆU! Hãy chạy file 'tao_dulieu.py' trước nhé.")
    st.stop() # Dừng chương trình lại

# --- 4. KHỞI TẠO LỊCH SỬ CHAT ---
# Biến session_state giúp Streamlit nhớ được tin nhắn cũ
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Chào bạn! Mình là AI Hướng dẫn viên tại Gành Đá Đĩa. Mình có thể giúp gì cho bạn?"}
    ]

# Hiển thị toàn bộ lịch sử chat ra màn hình
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# --- 5. XỬ LÝ KHI NGƯỜI DÙNG NHẬP CÂU HỎI ---
if question := st.chat_input("Nhập câu hỏi của bạn ở đây..."):
    # A. Hiện câu hỏi của người dùng ngay lập tức
    st.session_state.messages.append({"role": "user", "content": question})
    st.chat_message("user").write(question)

    # B. AI Xử lý và Trả lời
    if db:
        # Tìm kiếm 10 đoạn văn liên quan nhất (k=10 để không sót giá vé)
        docs = db.similarity_search(question, k=10)
        
        # Gom nội dung các đoạn văn lại
        context = "\n".join([d.page_content for d in docs])
        
        # Tạo câu lệnh Prompt (Nhồi thông tin vào cho AI học)
        prompt = f"""
        Bạn là Hướng dẫn viên du lịch chuyên nghiệp tại Gành Đá Đĩa (Phú Yên).
        Hãy trả lời câu hỏi của khách dựa trên thông tin dưới đây.
        
        THÔNG TIN TRA CỨU ĐƯỢC:
        {context}
        
        CÂU HỎI CỦA KHÁCH: {question}
        
        YÊU CẦU:
        1. Trả lời ngắn gọn, thân thiện, dùng icon cho sinh động.
        2. Nếu thông tin có trong bài, hãy trả lời chính xác.
        3. Nếu KHÔNG có thông tin trong bài, hãy nói khéo là chưa rõ, đừng bịa đặt.
        """
        
        # Gọi Gemini trả lời
        try:
            with st.spinner("Đang tra cứu cẩm nang du lịch..."):
                response = model.generate_content(prompt)
                answer = response.text
            
            # C. Hiện câu trả lời của AI
            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.chat_message("assistant").write(answer)
            
        except Exception as e:
            st.error(f"Úi, có lỗi kết nối rồi: {e}")