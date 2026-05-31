import logging
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.rag import pipeline

logger = logging.getLogger(__name__)


async def upload_and_index(
    file: UploadFile,
    course_id: str,
    user_id: str,
    db: Session,
) -> dict:
    file_bytes = await file.read()
    result     = pipeline.ingest(
        db         = db,
        file_bytes = file_bytes,
        filename   = file.filename,
        course_id  = course_id,
        user_id    = user_id,
    )
    return {
        "status":           result.status,
        "file_id":          result.file_id,
        "filename":         result.filename,
        "retrieval_chunks": result.retrieval_chunks,
        "parent_chunks":    result.parent_chunks,
        "text_chunks":      result.text_chunks,
        "table_chunks":     result.table_chunks,
        "image_chunks":     result.image_chunks,
        "error":            result.error,
    }


async def stream_answer(
    question: str,
    course_id: str,
    user_id: str,
    course_name: str,
    db: Session,
    history: list = None,
):
    async for event in pipeline.query(
        db          = db,
        user_query  = question,
        course_id   = course_id,
        user_id     = user_id,
        course_name = course_name,
        history     = history or [],
    ):
        yield event


def list_indexed_files(db: Session, course_id: str) -> list:
    return pipeline.list_course_files(db, course_id)


def delete_indexed_file(db: Session, file_id: str, course_id: str) -> dict:
    deleted_count = pipeline.delete_course_file(db, file_id, course_id)
    return {
        "file_id":       file_id,
        "deleted_count": deleted_count,
        "status":        "deleted" if deleted_count >= 0 else "not_found",
    }


def get_indexed_file_status(db: Session, file_id: str) -> dict:
    return pipeline.get_file_status(db, file_id)