from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from app.services.rag_service import save_uploaded_file
from app.services.rag_service import get_chat_answer, stream_chat_answer

router = APIRouter(prefix="/rag", tags=["rag"])

class ChatRequest(BaseModel):
    question: str
    course_id: str
    conversation_history: list = []

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), course_id: str = ...):  # ← ADD course_id parameter
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    save_dict = await save_uploaded_file(file, course_id)  # ← PASS course_id

    return {
        "message": f"Uploaded and indexed {save_dict['file_name']}",
        "file": save_dict,
    }

@router.post("/chat")
async def chat_with_rag(payload: ChatRequest):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    return get_chat_answer(payload.question, payload.course_id, payload.conversation_history)  # ← ADD course_id, history

@router.get("/chat/stream")  # ← ADD THIS NEW ENDPOINT
async def chat_stream(query: str, course_id: str):
    return StreamingResponse(
        stream_chat_answer(query, course_id),
        media_type="text/event-stream",
    )

@router.get("/files/{course_id}")
async def list_files(course_id: str):
    from app.services.rag_service import list_course_files
    return list_course_files(course_id)

@router.delete("/files/{course_id}/{file_id}")
async def delete_file(course_id: str, file_id: str):
    from app.services.rag_service import delete_course_file
    return {"deleted_chunks": delete_course_file(course_id, file_id)}