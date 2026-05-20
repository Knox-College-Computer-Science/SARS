"""
After the merger produces top-K chunk IDs, this module fetches the
corresponding ContextChunks and ParentChunks from the chunk store
and assembles RetrievedResult objects.
"""

import logging

from app.rag.models import RetrievalChunk, RetrievedResult
from app.rag.storage import chunk_store

logger = logging.getLogger("nexus.rag.lookup")


def enrich_results(
    top_results: list[dict],
    course_id:   str,
) -> list[RetrievedResult]:
    """
    For each result dict from the merger, fetch its ContextChunk and
    ParentChunk and package everything into a RetrievedResult.

    """
    if not top_results:
        return []

    # Batch-load all context chunks in one file read
    chunk_ids   = [r["chunk_id"] for r in top_results]
    ctx_map     = chunk_store.get_context_chunks_batch(course_id, chunk_ids)

    # Batch-load all parent chunks (deduplicated by parent_id)
    parent_ids  = list({
        ctx.parent_id
        for ctx in ctx_map.values()
    })
    parent_map  = chunk_store.get_parent_chunks_batch(course_id, parent_ids)

    # Assemble RetrievedResult objects
    results: list[RetrievedResult] = []
    for r in top_results:
        cid         = r["chunk_id"]
        meta        = r.get("metadata", {})
        ctx_chunk   = ctx_map.get(cid)
        parent_chunk = parent_map.get(ctx_chunk.parent_id) if ctx_chunk else None

        # Reconstruct a minimal RetrievalChunk from the ChromaDB metadata
        rc = RetrievalChunk(
            chunk_id        = cid,
            text            = r.get("document", ""),
            element_type    = meta.get("element_type", "text"),
            page_number     = meta.get("page_number", 0),
            section_heading = meta.get("section_heading", ""),
            chunk_index     = meta.get("chunk_index", 0),
            source_filename = meta.get("source_filename", ""),
            file_id         = meta.get("file_id", ""),
            course_id       = meta.get("course_id", course_id),
            user_id         = meta.get("user_id", ""),
            parent_id       = meta.get("parent_id", ""),
            formatted_content = meta.get("formatted_content", ""),
        )

        results.append(RetrievedResult(
            retrieval_chunk = rc,
            context_chunk   = ctx_chunk,
            parent_chunk    = parent_chunk,
            vector_score    = r.get("vector_score",   0.0),
            bm25_score      = r.get("bm25_score",     0.0),
            combined_score  = r.get("final_score",    r.get("combined_score", 0.0)),
        ))

    logger.debug(f"Enriched {len(results)} results with context + parent chunks")
    return results