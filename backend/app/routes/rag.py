from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.rag_service import (
    save_uploaded_file,
    stream_chat_answer,
    get_chat_answer,
    list_course_files,
    delete_course_file,
    get_file_status,
)

router = APIRouter(prefix="/rag", tags=["rag"])


class ChatRequest(BaseModel):
    question: str
    course_id: str
    conversation_history: list = []


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    course_id: str = Query(...),
    use_ocr: bool = Query(False),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    result = await save_uploaded_file(file, course_id, use_ocr=use_ocr)
    return {
        "message": f"Processed {result['file_name']}",
        "file": result,
    }


@router.get("/chat/stream")
async def chat_stream(
    query: str = Query(...),
    course_id: str = Query(...),
):
    return StreamingResponse(
        stream_chat_answer(query, course_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat")
async def chat(payload: ChatRequest):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    return get_chat_answer(
        payload.question,
        payload.course_id,
        payload.conversation_history,
    )


@router.get("/files/{course_id}")
async def list_files(course_id: str):
    files = list_course_files(course_id)
    return {"files": files, "course_id": course_id}


@router.delete("/files/{course_id}/{file_id}")
async def delete_file(course_id: str, file_id: str):
    deleted_count = delete_course_file(course_id, file_id)
    return {
        "deleted_chunks": deleted_count,
        "course_id": course_id,
        "file_id": file_id,
    }


@router.get("/status/{file_id}")
async def get_status(file_id: str):
    status = get_file_status(file_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"No status found for file_id={file_id}")
    return status