from fastapi import UploadFile
import os

from app.rag.rag_pipeline import index_pdf
from app.rag.rag_pipeline import answer_question

upload_folder = "RAG_Uploads"


def save_uploaded_file(file: UploadFile):
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    file_path = os.path.join(upload_folder, file.filename)

    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    with open(file_path, "rb") as saved_file:
        file_bytes = saved_file.read()

    index_result = index_pdf(file_bytes, file.filename)

    return {
        "file_path": file_path,
        "file_name": file.filename,
        "index_result": index_result,
    }

def get_chat_answer(question: str):
    return answer_question(question)