import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# 1. Cấu hình API Key (Dán mã của bạn vào đây)
MY_API_KEY = "HAY_DIEN_API_KEY_CUA_BAN_VAO_DAY"

# 2. Hàm đọc file dữ liệu
def nap_du_lieu():
    print("Đang đọc file dulieu_ganhdadie.txt...")
    
    # Kiểm tra file có tồn tại không
    if not os.path.exists("dulieu_ganhdadie.txt"):
        print("LỖI: Không tìm thấy file dulieu_ganhdadie.txt!")
        return

    # Đọc file
    with open("dulieu_ganhdadie.txt", "r", encoding="utf-8") as f:
        text = f.read()

    # Tách văn bản thành từng đoạn (dựa vào dòng trống)
    # Vì lúc soạn dữ liệu ta đã quy ước mỗi đoạn cách nhau 1 dòng trống
    cac_doan_van = text.split("\n\n")
    
    # Lọc bỏ các đoạn trống (nếu có)
    documents = []
    for doan in cac_doan_van:
        if doan.strip(): # Nếu đoạn văn có chữ
            doc = Document(page_content=doan)
            documents.append(doc)
            
    print(f"Đã tìm thấy {len(documents)} đoạn thông tin.")
    return documents

# 3. Hàm tạo Vector Database
def tao_vector_db(documents):
    if not documents:
        return

    print("Đang mã hóa dữ liệu (Embeddings)... Chờ chút nhé!")
    
    # Khởi tạo mô hình Embeddings của Google
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=MY_API_KEY)
    
    # Đưa dữ liệu vào FAISS (Vector DB)
    vector_db = FAISS.from_documents(documents, embeddings)
    
    # Lưu xuống ổ cứng để dùng lại sau này
    vector_db.save_local("faiss_index")
    print("XONG! Dữ liệu đã được lưu vào thư mục 'faiss_index'")

# --- CHẠY CHƯƠNG TRÌNH ---
if __name__ == "__main__":
    docs = nap_du_lieu()
    if docs:
        tao_vector_db(docs)