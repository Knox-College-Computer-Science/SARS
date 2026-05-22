from typing import List

import logging

from app.rag.models import RetrievalChunk, RetrievedResult
from app.rag.storage import chunk_store

logger = logging.getLogger("sars.rag.lookup")


def fetch_parents(
    top_results: List[dict],
    course_id:   str,
) -> List[RetrievedResult]:
    if not top_results:
        return []

    # Collect unique parent_ids from ChromaDB metadata
    parent_ids = list({
        r.get("metadata", {}).get("parent_id", "")
        for r in top_results
        if r.get("metadata", {}).get("parent_id")
    })

    # Batch-load all parent chunks in one file read
    parent_map = chunk_store.get_parent_chunks_batch(course_id, parent_ids)

    results: List[RetrievedResult] = []
    for r in top_results:
        meta       = r.get("metadata", {})
        parent_id  = meta.get("parent_id", "")
        parent_chunk = parent_map.get(parent_id)

        # Reconstruct a RetrievalChunk from ChromaDB metadata
        rc = RetrievalChunk(
            chunk_id          = r["chunk_id"],
            text              = r.get("document", ""),
            element_type      = meta.get("element_type", "text"),
            page_number       = meta.get("page_number", 0),
            section_heading   = meta.get("section_heading", ""),
            chunk_index       = meta.get("chunk_index", 0),
            source_filename   = meta.get("source_filename", ""),
            file_id           = meta.get("file_id", ""),
            course_id         = meta.get("course_id", course_id),
            user_id           = meta.get("user_id", ""),
            parent_id         = parent_id,
            formatted_content = meta.get("formatted_content", ""),
        )

        results.append(RetrievedResult(
            retrieval_chunk = rc,
            context_chunk   = None,   # ContextChunk removed
            parent_chunk    = parent_chunk,
            vector_score    = r.get("vector_score",  0.0),
            bm25_score      = r.get("bm25_score",    0.0),
            combined_score  = r.get("final_score",   r.get("combined_score", 0.0)),
        ))

    logger.debug(f"Fetched {len(results)} results with parent chunks")
    return results