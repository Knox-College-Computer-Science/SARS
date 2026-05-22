import uuid
from fastapi import UploadFile

from app.rag import pipeline
from app.rag import config as rag_config


async def save_uploaded_file(
    file: UploadFile,
    course_id: str,
    use_ocr: bool = False,
) -> dict:
    file_bytes = await file.read()   # async read — non-blocking
    file_id    = str(uuid.uuid4())

    original_strategy = rag_config.EXTRACTION_STRATEGY
    if use_ocr:
        rag_config.EXTRACTION_STRATEGY = "hi_res"

    try:
        index_result = pipeline.index_document(
            file_bytes = file_bytes,
            filename   = file.filename,
            course_id  = course_id,
            user_id    = "current_user",   # Replace with actual user from auth
            file_id    = file_id,
        )
    finally:
        rag_config.EXTRACTION_STRATEGY = original_strategy

    return {
        "file_name": file.filename,
        "file_id":   file_id,
        "index_result": {
            "status":           index_result.status,
            "retrieval_chunks": index_result.retrieval_chunks,
            "parent_chunks":    index_result.parent_chunks,
            "text_chunks":      index_result.text_chunks,
            "table_chunks":     index_result.table_chunks,
            "image_chunks":     index_result.image_chunks,
            "error":            index_result.error,
        },
    }


def stream_chat_answer(question: str, course_id: str, conversation_history: list = None):
    return pipeline.stream_answer(question, course_id, conversation_history or [])


def get_chat_answer(question: str, course_id: str, conversation_history: list = None) -> dict:
    return pipeline.answer_question(question, course_id, conversation_history or [])


def list_course_files(course_id: str) -> list:
    return pipeline.list_course_files(course_id)


def delete_course_file(course_id: str, file_id: str) -> int:
    return pipeline.delete_course_file(course_id, file_id)


def get_file_status(file_id: str) -> dict:
    return pipeline.get_document_status(file_id)