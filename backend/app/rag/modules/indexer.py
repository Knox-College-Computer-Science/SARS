from typing import List

import logging

from app.rag.models import (
    RetrievalChunk,
    ParentChunk,
    IndexResult,
)
from app.rag.modules.embedder import embed_texts
from app.rag.storage.vector_store import upsert_chunks
from app.rag.storage import chunk_store

logger = logging.getLogger("sars.rag.indexer")


def index_all(
    retrieval_chunks:  List[RetrievalChunk],
    parent_chunks:     List[ParentChunk],
    file_id:           str,
    filename:          str,
    course_id:         str,
    md5_hash:          str = "",
) -> IndexResult:
    result = IndexResult(
        file_id          = file_id,
        filename         = filename,
        course_id        = course_id,
        parent_chunks    = len(parent_chunks),
        retrieval_chunks = len(retrieval_chunks),
        text_chunks      = sum(1 for c in retrieval_chunks if c.element_type == "text"),
        table_chunks     = sum(1 for c in retrieval_chunks if c.element_type == "table"),
        image_chunks     = sum(1 for c in retrieval_chunks if c.element_type == "image"),
    )

    if not retrieval_chunks:
        result.status = "error"
        result.error  = "No retrieval chunks produced — document may be empty or image-only."
        return result

    try:
        #  Step 1: Embed retrieval chunk texts
        texts = [c.text for c in retrieval_chunks]
        logger.info(f"Embedding {len(texts)} chunks for {filename}…")
        embeddings = embed_texts(texts)

        #  Step 2: Upsert into ChromaDB
        upsert_chunks(
            course_id  = course_id,
            ids        = [c.chunk_id for c in retrieval_chunks],
            embeddings = embeddings,
            documents  = texts,
            metadatas  = [c.to_chroma_metadata() for c in retrieval_chunks],
        )
        logger.info(f"Indexed {len(retrieval_chunks)} chunks into ChromaDB (course: {course_id})")

        #  Step 3: Save parent chunks
        chunk_store.save_parent_chunks(course_id, parent_chunks)

        #  Step 4: Store file metadata for duplicate detection
        chunk_store.save_file_metadata(course_id, {
            "file_id":   file_id,
            "filename":  filename,
            "md5_hash":  md5_hash,
            "course_id": course_id,
        })

    except Exception as e:
        logger.error(f"Indexing failed for {filename}: {e}", exc_info=True)
        result.status = "error"
        result.error  = str(e)

    return result