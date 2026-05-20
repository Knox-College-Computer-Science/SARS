import logging

from app.rag.models import (
    RetrievalChunk,
    ContextChunk,
    ParentChunk,
    IndexResult,
)
from app.rag.modules.embedder import embed_texts
from app.rag.storage.vector_store import upsert_chunks
from app.rag.storage import chunk_store

logger = logging.getLogger("nexus.rag.indexer")


def index_all(
    retrieval_chunks:  list[RetrievalChunk],
    context_chunks:    dict[str, ContextChunk],
    parent_chunks:     list[ParentChunk],
    file_id:           str,
    filename:          str,
    course_id:         str,
) -> IndexResult:
    """
    Embed and store all three chunk types.

    Called by pipeline.index_document() after chunking and enrichment.

    Returns an IndexResult summarising what was stored.
    """
    result = IndexResult(
        file_id  = file_id,
        filename = filename,
        course_id= course_id,
        parent_chunks    = len(parent_chunks),
        retrieval_chunks = len(retrieval_chunks),
        text_chunks  = sum(1 for c in retrieval_chunks if c.element_type == "text"),
        table_chunks = sum(1 for c in retrieval_chunks if c.element_type == "table"),
        image_chunks = sum(1 for c in retrieval_chunks if c.element_type == "image"),
    )

    if not retrieval_chunks:
        result.status = "error"
        result.error  = "No retrieval chunks produced — document may be empty or image-only."
        return result

    try:
        # ── Step 1: Embed retrieval chunk texts ──────────────────
        # We embed the CLEAN text (not the enriched context text).
        # Clean embeddings = better semantic signal.
        texts = [c.text for c in retrieval_chunks]
        logger.info(f"Embedding {len(texts)} chunks for {filename}…")
        embeddings = embed_texts(texts)

        # ── Step 2: Upsert into ChromaDB ─────────────────────────
        upsert_chunks(
            course_id  = course_id,
            ids        = [c.chunk_id for c in retrieval_chunks],
            embeddings = embeddings,
            documents  = texts,
            metadatas  = [c.to_chroma_metadata() for c in retrieval_chunks],
        )
        logger.info(f"Indexed {len(retrieval_chunks)} chunks into ChromaDB (course: {course_id})")

        # ── Step 3: Save context chunks ───────────────────────────
        chunk_store.save_context_chunks(course_id, context_chunks)

        # ── Step 4: Save parent chunks ────────────────────────────
        chunk_store.save_parent_chunks(course_id, parent_chunks)

    except Exception as e:
        logger.error(f"Indexing failed for {filename}: {e}", exc_info=True)
        result.status = "error"
        result.error  = str(e)

    return result