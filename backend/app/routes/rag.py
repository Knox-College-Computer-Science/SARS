from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.services.rag_service import save_uploaded_file
from app.services.rag_service import get_chat_answer

router = APIRouter(prefix="/rag", tags=["rag"])

class ChatRequest(BaseModel):
    question: str

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    save_dict = save_uploaded_file(file)

    return {
        "message": f"Uploaded and indexed {save_dict['file_name']}",
        "file": save_dict,
    }

@router.post("/chat")
async def chat_with_rag(payload: ChatRequest):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    return get_chat_answer(payload.question)

