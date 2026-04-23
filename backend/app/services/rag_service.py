from pathlib import Path
from fastapi import UploadFile

from app.rag.rag_pipeline import index_pdf, answer_question

UPLOAD_FOLDER = Path(__file__).resolve().parent.parent.parent / "RAG_Uploads"


def save_uploaded_file(file: UploadFile):
    UPLOAD_FOLDER.mkdir(exist_ok=True)
    file_path = UPLOAD_FOLDER / file.filename
    file_bytes = file.file.read()

    with open(file_path, "wb") as buffer:
        buffer.write(file_bytes)

    index_result = index_pdf(file_bytes, file.filename)

    return {
        "file_path": str(file_path),
        "file_name": file.filename,
        "index_result": index_result,
    }


def get_chat_answer(question: str):
    return answer_question(question)
