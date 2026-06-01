import json
import logging
import math
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.rag.models import (
    ParentChunkData,
    RAGFile,
    RetrievalChunk,
    RetrievalChunkData,
    ParentChunk,
    RetrievedResult,
)
from app.rag.config import VECTOR_SEARCH_TOP_K

logger = logging.getLogger(__name__)


### SIMILARITY ###

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot    = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _is_postgres(db: Session) -> bool:
    return "postgresql" in str(db.bind.url)


### WRITE ###

def save_chunks(
    db: Session,
    retrieval_chunks: List[RetrievalChunkData],
    parent_chunks: List[ParentChunkData],
    embeddings: List[List[float]],
    file_id: str,
    course_id: str,
) -> None:
    if len(retrieval_chunks) != len(embeddings):
        raise ValueError(
            f"Chunk count ({len(retrieval_chunks)}) != "
            f"embedding count ({len(embeddings)})"
        )

    for parent_data in parent_chunks:
        existing = (
            db.query(ParentChunk)
            .filter(ParentChunk.parent_id == parent_data.parent_id)
            .first()
        )
        if existing:
            continue

        db.add(ParentChunk(
            parent_id        = parent_data.parent_id,
            course_id        = course_id,
            file_id          = file_id,
            section_heading  = parent_data.section_heading,
            page_number      = parent_data.page_number,
            page_range_start = parent_data.page_range[0],
            page_range_end   = parent_data.page_range[1],
            source_filename  = parent_data.source_filename,
            text             = parent_data.text,
            child_chunk_ids  = parent_data.child_chunk_ids,
        ))

    for chunk_data, embedding in zip(retrieval_chunks, embeddings):
        existing = (
            db.query(RetrievalChunk)
            .filter(RetrievalChunk.chunk_id == chunk_data.chunk_id)
            .first()
        )
        if existing:
            existing.embedding = embedding
            continue

        db.add(RetrievalChunk(
            chunk_id          = chunk_data.chunk_id,
            course_id         = course_id,
            user_id           = chunk_data.user_id,
            file_id           = file_id,
            parent_id         = chunk_data.parent_id,
            chunk_index       = chunk_data.chunk_index,
            element_type      = chunk_data.element_type,
            page_number       = chunk_data.page_number,
            section_heading   = chunk_data.section_heading,
            source_filename   = chunk_data.source_filename,
            text              = chunk_data.text,
            formatted_content = chunk_data.formatted_content,
            embedding         = embedding,
        ))

    db.commit()
    logger.info(
        f"Saved {len(parent_chunks)} parent chunks and "
        f"{len(retrieval_chunks)} retrieval chunks for file {file_id}"
    )


### READ ###

def search_vectors(
    db: Session,
    query_embedding: List[float],
    course_id: str,
    top_k: int = VECTOR_SEARCH_TOP_K,
) -> List[Tuple[RetrievalChunkData, float]]:
    if _is_postgres(db):
        return _search_pgvector(db, query_embedding, course_id, top_k)
    return _search_sqlite(db, query_embedding, course_id, top_k)


def _search_pgvector(
    db: Session,
    query_embedding: List[float],
    course_id: str,
    top_k: int,
) -> List[Tuple[RetrievalChunkData, float]]:
    from sqlalchemy import text

    vector_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    rows = db.execute(
        text("""
            SELECT
                chunk_id, course_id, user_id, file_id, parent_id,
                chunk_index, element_type, page_number, section_heading,
                source_filename, text, formatted_content,
                1 - (embedding <=> :query_vec::vector) AS score
            FROM retrieval_chunks
            WHERE course_id = :course_id
            ORDER BY embedding <=> :query_vec::vector
            LIMIT :top_k
        """),
        {"query_vec": vector_str, "course_id": course_id, "top_k": top_k},
    ).fetchall()

    return [(_row_to_chunk(row), float(row.score)) for row in rows]


def _search_sqlite(
    db: Session,
    query_embedding: List[float],
    course_id: str,
    top_k: int,
) -> List[Tuple[RetrievalChunkData, float]]:
    rows = (
        db.query(RetrievalChunk)
        .filter(RetrievalChunk.course_id == course_id)
        .filter(RetrievalChunk.embedding.isnot(None))
        .all()
    )

    scored = []
    for row in rows:
        embedding = row.embedding
        if isinstance(embedding, str):
            embedding = json.loads(embedding)
        score = _cosine_similarity(query_embedding, embedding)
        scored.append((_orm_to_chunk(row), score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


### PARENT FETCH ###

def fetch_parent(db: Session, parent_id: str) -> Optional[ParentChunkData]:
    row = (
        db.query(ParentChunk)
        .filter(ParentChunk.parent_id == parent_id)
        .first()
    )
    if not row:
        return None
    return ParentChunkData(
        parent_id       = row.parent_id,
        text            = row.text,
        source_filename = row.source_filename,
        course_id       = row.course_id,
        file_id         = row.file_id,
        section_heading = row.section_heading or "",
        page_number     = row.page_number or 0,
        page_range      = (row.page_range_start or 0, row.page_range_end or 0),
        child_chunk_ids = row.child_chunk_ids or [],
        created_at      = row.created_at.isoformat() if row.created_at else "",
    )


def fetch_siblings(
    db: Session,
    parent_id: str,
    chunk_index: int,
) -> Tuple[Optional[RetrievalChunkData], Optional[RetrievalChunkData]]:
    prev_row = (
        db.query(RetrievalChunk)
        .filter(
            RetrievalChunk.parent_id == parent_id,
            RetrievalChunk.chunk_index == chunk_index - 1,
        )
        .first()
    )
    next_row = (
        db.query(RetrievalChunk)
        .filter(
            RetrievalChunk.parent_id == parent_id,
            RetrievalChunk.chunk_index == chunk_index + 1,
        )
        .first()
    )
    return (
        _orm_to_chunk(prev_row) if prev_row else None,
        _orm_to_chunk(next_row) if next_row else None,
    )


### DELETE ###

def delete_file_chunks(db: Session, file_id: str) -> int:
    deleted = (
        db.query(RetrievalChunk)
        .filter(RetrievalChunk.file_id == file_id)
        .delete()
    )
    db.query(ParentChunk).filter(ParentChunk.file_id == file_id).delete()
    db.commit()
    logger.info(f"Deleted {deleted} retrieval chunks for file {file_id}")
    return deleted


### HELPERS ###

def _orm_to_chunk(row: RetrievalChunk) -> RetrievalChunkData:
    return RetrievalChunkData(
        chunk_id          = row.chunk_id,
        text              = row.text,
        element_type      = row.element_type,
        page_number       = row.page_number or 0,
        section_heading   = row.section_heading or "",
        chunk_index       = row.chunk_index,
        source_filename   = row.source_filename,
        filename          = row.source_filename,
        file_id           = row.file_id,
        course_id         = row.course_id,
        user_id           = row.user_id,
        parent_id         = row.parent_id,
        formatted_content = row.formatted_content or "",
    )


def _row_to_chunk(row) -> RetrievalChunkData:
    return RetrievalChunkData(
        chunk_id          = row.chunk_id,
        text              = row.text,
        element_type      = row.element_type,
        page_number       = row.page_number or 0,
        section_heading   = row.section_heading or "",
        chunk_index       = row.chunk_index,
        source_filename   = row.source_filename,
        filename          = row.source_filename,
        file_id           = row.file_id,
        course_id         = row.course_id,
        user_id           = row.user_id,
        parent_id         = row.parent_id,
        formatted_content = row.formatted_content or "",
    )