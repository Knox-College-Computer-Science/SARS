from pathlib import Path
from fastapi import UploadFile
import uuid

from app.rag import pipeline  # ← CHANGE THIS (was: from app.rag.rag_pipeline)

UPLOAD_FOLDER = Path(__file__).resolve().parent.parent.parent / "RAG_Uploads"


async def save_uploaded_file(file: UploadFile, course_id: str):  # ← ADD course_id
    """Save and index a PDF file for a specific course."""
    UPLOAD_FOLDER.mkdir(exist_ok=True)
    file_path = UPLOAD_FOLDER / file.filename
    file_bytes = await file.read()  # ← Make it async

    # Save to disk
    with open(file_path, "wb") as buffer:
        buffer.write(file_bytes)

    # Index using new pipeline with course_id
    file_id = str(uuid.uuid4())
    index_result = pipeline.index_document(
        file_bytes=file_bytes,
        filename=file.filename,
        course_id=course_id,  # ← NEW
        user_id="current_user",  # ← NEW (get from auth later)
        file_id=file_id,  # ← NEW
    )

    return {
        "file_path": str(file_path),
        "file_name": file.filename,
        "file_id": file_id,  # ← NEW
        "index_result": {
            "status": index_result.status,
            "retrieval_chunks": index_result.retrieval_chunks,
            "parent_chunks": index_result.parent_chunks,
            "error": index_result.error,
        },
    }


def get_chat_answer(question: str, course_id: str, conversation_history: list = None):  # ← ADD course_id, history
    """Non-streaming chat answer (for testing/simple endpoints)."""
    if conversation_history is None:
        conversation_history = []

    return pipeline.answer_question(question, course_id, conversation_history)  # ← PASS all params


def stream_chat_answer(question: str, course_id: str, conversation_history: list = None):  # ← ADD THIS NEW FUNCTION
    """Streaming chat answer (SSE events)."""
    if conversation_history is None:
        conversation_history = []

    return pipeline.stream_answer(question, course_id, conversation_history)


def list_course_files(course_id: str):  # ← ADD THIS NEW FUNCTION
    """List all indexed files for a course."""
    return pipeline.list_course_files(course_id)


def delete_course_file(course_id: str, file_id: str):  # ← ADD THIS NEW FUNCTION
    """Delete a file and all its chunks."""
    return pipeline.delete_course_file(course_id, file_id)