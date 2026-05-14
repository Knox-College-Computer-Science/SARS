"""
Takes RetrievalChunks and produces ContextChunks
"""

import logging

from app.rag.models import RetrievalChunk, ContextChunk

logger = logging.getLogger("SARS.rag.context_chunk")


def create_context_chunks(
    retrieval_chunks: list[RetrievalChunk],
) -> dict[str, ContextChunk]:
    """
    Build a ContextChunk for every RetrievalChunk.

    """
    contexts: dict[str, ContextChunk] = {}

    for rc in retrieval_chunks:
        header        = _build_header(rc)
        enriched_text = header + rc.text
        citation      = _build_citation(rc)

        contexts[rc.chunk_id] = ContextChunk(
            chunk_id        = rc.chunk_id,
            text            = enriched_text,
            parent_id       = rc.parent_id,
            source_filename = rc.source_filename,
            section_heading = rc.section_heading,
            page_number     = rc.page_number,
            element_type    = rc.element_type,
            citation_label  = citation,
        )

    logger.debug(f"Created {len(contexts)} context chunks")
    return contexts


def _build_header(rc: RetrievalChunk) -> str:

    parts = [f"Source: {rc.source_filename}"]

    if rc.section_heading:
        parts.append(f"Section: {rc.section_heading}")

    parts.append(f"Page: {rc.page_number}")
    parts.append(f"Type: {rc.element_type}")

    return "[" + " | ".join(parts) + "]\n\n"


def _build_citation(rc: RetrievalChunk) -> str:

    section_part = f" — {rc.section_heading}" if rc.section_heading else ""
    return f"{rc.source_filename}{section_part}, p.{rc.page_number} ({rc.element_type})"