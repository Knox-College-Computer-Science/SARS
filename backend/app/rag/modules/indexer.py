import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.rag.models import IndexResult, RAGFile
from app.rag.modules.extractor import extract, compute_md5
from app.rag.modules.chunker import chunk, assess_quality
from app.rag.modules.embedder import embed_texts
from app.rag.storage.vector_store import save_chunks, delete_file_chunks

logger = logging.getLogger(__name__)


### HELPERS ###

def _get_or_create_rag_file(
    db: Session,
    file_id: str,
    course_id: str,
    user_id: str,
    filename: str,
    md5_hash: str,
    drive_file_id: Optional[str],
    local_path: Optional[str],
    file_size: int,
) -> Optional[RAGFile]:
    existing = db.query(RAGFile).filter(RAGFile.md5_hash == md5_hash).first()
    if existing:
        return None

    rag_file = RAGFile(
        id              = file_id,
        course_id       = course_id,
        user_id         = user_id,
        filename        = filename,
        source_type     = "uploaded",
        drive_file_id   = drive_file_id,
        local_path      = local_path,
        md5_hash        = md5_hash,
        file_size       = file_size,
        indexing_status = "processing",
    )
    db.add(rag_file)
    db.commit()
    return rag_file


def _mark_indexed(db: Session, file_id: str, quality: dict) -> None:
    rag_file = db.query(RAGFile).filter(RAGFile.id == file_id).first()
    if rag_file:
        rag_file.indexing_status    = "indexed"
        rag_file.indexed_at         = datetime.utcnow()
        rag_file.quality_assessment = quality
        rag_file.warnings           = quality.get("warnings", [])
        db.commit()


def _mark_failed(db: Session, file_id: str, error: str) -> None:
    rag_file = db.query(RAGFile).filter(RAGFile.id == file_id).first()
    if rag_file:
        rag_file.indexing_status = "failed"
        rag_file.warnings        = [error]
        db.commit()


### PUBLIC API ###

def index_file(
    db: Session,
    file_bytes: bytes,
    filename: str,
    file_id: str,
    course_id: str,
    user_id: str,
    drive_file_id: Optional[str] = None,
    local_path: Optional[str] = None,
    is_slides: bool = False,
) -> IndexResult:
    md5 = compute_md5(file_bytes)

    rag_file = _get_or_create_rag_file(
        db            = db,
        file_id       = file_id,
        course_id     = course_id,
        user_id       = user_id,
        filename      = filename,
        md5_hash      = md5,
        drive_file_id = drive_file_id,
        local_path    = local_path,
        file_size     = len(file_bytes),
    )

    if rag_file is None:
        logger.info(f"Duplicate detected for {filename} ({md5[:8]})")
        return IndexResult(
            file_id  = file_id,
            filename = filename,
            course_id = course_id,
            status   = "duplicate",
        )

    try:
        elements = extract(file_bytes, filename)
        quality  = assess_quality(elements)

        if quality["tier"] == "empty":
            _mark_failed(db, file_id, "Document contains no extractable text")
            return IndexResult(
                file_id   = file_id,
                filename  = filename,
                course_id = course_id,
                status    = "error",
                error     = "Document contains no extractable text",
            )

        parents, retrieval_chunks = chunk(
            elements  = elements,
            file_id   = file_id,
            course_id = course_id,
            user_id   = user_id,
            filename  = filename,
            is_slides = is_slides,
        )

        if not retrieval_chunks:
            _mark_failed(db, file_id, "No chunks produced after parsing")
            return IndexResult(
                file_id   = file_id,
                filename  = filename,
                course_id = course_id,
                status    = "error",
                error     = "No chunks produced after parsing",
            )

        texts      = [c.text for c in retrieval_chunks]
        embeddings = embed_texts(texts)

        save_chunks(
            db               = db,
            retrieval_chunks = retrieval_chunks,
            parent_chunks    = parents,
            embeddings       = embeddings,
            file_id          = file_id,
            course_id        = course_id,
        )

        _mark_indexed(db, file_id, quality)

        text_count  = sum(1 for c in retrieval_chunks if c.element_type == "text")
        table_count = sum(1 for c in retrieval_chunks if c.element_type == "table")
        image_count = sum(1 for c in retrieval_chunks if c.element_type == "image")

        logger.info(
            f"Indexed {filename}: {len(retrieval_chunks)} chunks "
            f"(text={text_count}, table={table_count}, image={image_count})"
        )

        return IndexResult(
            file_id          = file_id,
            filename         = filename,
            course_id        = course_id,
            total_elements   = len(elements),
            parent_chunks    = len(parents),
            retrieval_chunks = len(retrieval_chunks),
            text_chunks      = text_count,
            table_chunks     = table_count,
            image_chunks     = image_count,
            status           = "success",
        )

    except Exception as e:
        logger.error(f"Indexing failed for {filename}: {e}", exc_info=True)
        _mark_failed(db, file_id, str(e))
        try:
            delete_file_chunks(db, file_id)
        except Exception:
            pass
        return IndexResult(
            file_id   = file_id,
            filename  = filename,
            course_id = course_id,
            status    = "error",
            error     = str(e),
        )