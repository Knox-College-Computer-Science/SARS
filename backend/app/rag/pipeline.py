import logging
import time
import uuid
from typing import AsyncGenerator, List, Optional

from sqlalchemy.orm import Session

from app.rag.models import IndexResult, RAGFile, RetrievedResult
from app.rag.modules.indexer import index_file
from app.rag.modules.retriever import retrieve, invalidate_bm25_cache
from app.rag.modules.reranker import rerank, assess_confidence
from app.rag.modules.context_packer import pack
from app.rag.modules.multi_query import expand_query, detect_intent
from app.rag.modules.prompt_builder import build_messages
from app.rag.modules.generator import stream
from app.rag.storage.vector_store import delete_file_chunks
from app.rag.config import EVAL_LOG_ENABLED

logger = logging.getLogger(__name__)


### WRITE PATH ###

def ingest(
        db: Session,
        file_bytes: bytes,
        filename: str,
        course_id: str,
        user_id: str,
        drive_file_id: Optional[str] = None,
        local_path: Optional[str] = None,
        file_id: Optional[str] = None,
) -> IndexResult:
    file_id = file_id or str(uuid.uuid4())
    is_slides = filename.lower().endswith(".pptx")

    result = index_file(
        db=db,
        file_bytes=file_bytes,
        filename=filename,
        file_id=file_id,
        course_id=course_id,
        user_id=user_id,
        drive_file_id=drive_file_id,
        local_path=local_path,
        is_slides=is_slides,
    )

    if result.status == "success":
        invalidate_bm25_cache(course_id)

    return result


### READ PATH ###

async def query(
        db: Session,
        user_query: str,
        course_id: str,
        user_id: str,
        course_name: str,
        history: Optional[List[dict]] = None,
) -> AsyncGenerator[dict, None]:
    history = history or []
    start = time.time()

    intent = detect_intent(user_query)
    variants = expand_query(user_query)

    retrieved = retrieve(
        db=db,
        query=user_query,
        query_variants=variants,
        course_id=course_id,
    )

    reranked = await rerank(user_query, retrieved)
    confidence = assess_confidence(reranked)

    context_block, selected = pack(reranked)

    citations = [
        {
            "source": r.retrieval_chunk.source_filename,
            "section": r.retrieval_chunk.section_heading,
            "page": r.retrieval_chunk.page_number,
            "element_type": r.retrieval_chunk.element_type,
        }
        for r in selected
    ]

    yield {"type": "citations", "citations": citations}

    messages = build_messages(
        query=user_query,
        context_block=context_block,
        history=history,
        course_name=course_name,
        confidence=confidence,
        intent=intent,
    )

    full_response = ""
    async for token in stream(messages):
        full_response += token
        yield {"type": "token", "text": token}

    yield {"type": "done"}

    latency_ms = (time.time() - start) * 1000

    if EVAL_LOG_ENABLED:
        _log_retrieval(
            db=db,
            course_id=course_id,
            user_id=user_id,
            query=user_query,
            variants=variants,
            results=reranked,
            confidence=confidence,
            latency_ms=latency_ms,
        )


### FILE MANAGEMENT ###

def list_course_files(db: Session, course_id: str) -> list:
    files = (
        db.query(RAGFile)
        .filter(RAGFile.course_id == course_id)
        .filter(RAGFile.indexing_status != "deleted")
        .order_by(RAGFile.created_at.desc())
        .all()
    )
    return [
        {
            "file_id": f.id,
            "filename": f.filename,
            "indexing_status": f.indexing_status,
            "indexed_at": f.indexed_at.isoformat() if f.indexed_at else None,
            "quality_tier": f.quality_assessment.get("tier") if f.quality_assessment else None,
            "warnings": f.warnings or [],
            "file_size": f.file_size,
            "drive_file_id": f.drive_file_id,
            "labels": f.labels or [],
            "source_type": f.source_type,  
        }
        for f in files
    ]


def delete_course_file(db: Session, file_id: str, course_id: str) -> int:
    rag_file = (
        db.query(RAGFile)
        .filter(RAGFile.id == file_id, RAGFile.course_id == course_id)
        .first()
    )

    if not rag_file:
        logger.warning(f"File {file_id} not found in course {course_id}")
        return 0

    deleted = delete_file_chunks(db, file_id)

    rag_file.indexing_status = "deleted"
    db.commit()

    invalidate_bm25_cache(course_id)

    logger.info(f"Deleted file {file_id}: {deleted} chunks removed")
    return deleted


def get_file_status(db: Session, file_id: str) -> dict:
    rag_file = db.query(RAGFile).filter(RAGFile.id == file_id).first()

    if not rag_file:
        return {"status": "not_found"}

    return {
        "file_id": rag_file.id,
        "filename": rag_file.filename,
        "status": rag_file.indexing_status,
        "indexed_at": rag_file.indexed_at.isoformat() if rag_file.indexed_at else None,
        "quality_tier": rag_file.quality_assessment.get("tier") if rag_file.quality_assessment else None,
        "warnings": rag_file.warnings or [],
        "file_size": rag_file.file_size,
    }


### EVAL LOGGING ###

def _log_retrieval(
        db: Session,
        course_id: str,
        user_id: str,
        query: str,
        variants: List[str],
        results: List[RetrievedResult],
        confidence: str,
        latency_ms: float,
) -> None:
    try:
        from app.rag.models import RAGRetrievalLog
        log = RAGRetrievalLog(
            course_id=course_id,
            user_id=user_id,
            query=query,
            query_variants=variants,
            retrieval_latency_ms=latency_ms,
            num_results=len(results),
            confidence_level=confidence,
            hit_at_5=len(results) >= 1,
            retrieved_chunk_ids=[r.retrieval_chunk.chunk_id for r in results],
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning(f"Retrieval logging failed: {e}")