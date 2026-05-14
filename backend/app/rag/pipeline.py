import logging
import time
import uuid
from pathlib import Path
from typing import Iterator, Optional

from app.rag.config import UPLOAD_DIR
from app.rag.models import IndexResult
from app.rag.modules.extractor    import extract_elements
from app.rag.modules.chunker      import chunk_document
from app.rag.modules.context_chunk     import create_context_chunks
from app.rag.modules.indexer      import index_all
from app.rag.modules.multi_query     import generate_query_variants
from app.rag.modules.retriever    import retrieve_for_query
from app.rag.modules.merger       import merge_results
from app.rag.modules.lookup       import enrich_results
from app.rag.modules.prompt_builder import build_prompt
from app.rag.modules.generator    import stream_response
from app.rag.storage              import vector_store, chunk_store, eval_store

logger = logging.getLogger("SARS.rag.pipeline")

### INGESTION ###

def index_document(
    file_bytes: bytes,
    filename:   str,
    course_id:  str,
    user_id:    str = "anonymous",
    file_id:    Optional[str] = None,
) -> IndexResult:

    if file_id is None:
        file_id = str(uuid.uuid4())

    logger.info(f"[INGEST] Starting: {filename} → course {course_id}")
    t_start = time.time()

    # ── Save raw file to disk ────────────────────────────────────
    _save_to_disk(file_bytes, filename, file_id)

    # ── Extract ──────────────────────────────────────────────────
    try:
        elements = extract_elements(file_bytes, filename)
    except ValueError as e:
        return IndexResult(
            file_id=file_id, filename=filename, course_id=course_id,
            status="error", error=str(e),
        )

    if not elements:
        return IndexResult(
            file_id=file_id, filename=filename, course_id=course_id,
            status="error",
            error="No content extracted. Is this a scanned image-only PDF?",
        )

    # ── Chunk (all three tiers) ───────────────────────────────────
    parent_chunks, retrieval_chunks = chunk_document(
        elements  = elements,
        filename  = filename,
        file_id   = file_id,
        course_id = course_id,
        user_id   = user_id,
    )

    # ── Enrich (create context chunks) ───────────────────────────
    context_chunks = create_context_chunks(retrieval_chunks)

    # ── Index (embed + store all three tiers) ────────────────────
    result = index_all(
        retrieval_chunks = retrieval_chunks,
        context_chunks   = context_chunks,
        parent_chunks    = parent_chunks,
        file_id          = file_id,
        filename         = filename,
        course_id        = course_id,
    )

    result.total_elements = len(elements)
    elapsed = time.time() - t_start
    logger.info(
        f"[INGEST] Done: {filename} in {elapsed:.1f}s — "
        f"{result.retrieval_chunks} retrieval chunks, "
        f"{result.parent_chunks} parents, status={result.status}"
    )
    return result



### RETRIEVAL + GENERATION ###


def stream_answer(
    query:                str,
    course_id:            str,
    conversation_history: Optional[list[dict]] = None,
) -> Iterator[str]:
    """
    Full retrieval + generation pipeline. Yields SSE event strings.

    """
    import json

    if conversation_history is None:
        conversation_history = []

    t0 = time.time()

    # ── 1. Expand query ──────────────────────────────────────────
    variants = generate_query_variants(query)

    # ── 2. Hybrid search for each variant ────────────────────────
    all_raw_results = [
        retrieve_for_query(variant, course_id)
        for variant in variants
    ]

    # ── 3. Merge + deduplicate ───────────────────────────────────
    top_raw = merge_results(all_raw_results)

    retrieval_latency_ms = (time.time() - t0) * 1000

    if not top_raw:
        yield _no_docs_event()
        return

    # ── 4. Enrich with context + parent chunks ───────────────────
    retrieved = enrich_results(top_raw, course_id)

    # ── 5. Log retrieval for evaluation ─────────────────────────
    eval_store.log_retrieval(
        query                = query,
        course_id            = course_id,
        query_variants       = variants,
        results              = retrieved,
        retrieval_latency_ms = retrieval_latency_ms,
    )

    # ── 6. Build prompt ──────────────────────────────────────────
    messages = build_prompt(query, retrieved, conversation_history)

    # ── 7. Stream answer ─────────────────────────────────────────
    yield from stream_response(messages, retrieved)


def answer_question(
    query:                str,
    course_id:            str,
    conversation_history: Optional[list[dict]] = None,
) -> dict:
    """
    Non-streaming version. Collects the full SSE stream and returns a dict.

    """
    import json

    if conversation_history is None:
        conversation_history = []

    answer_tokens: list[str] = []
    citations: list[dict]    = []

    for event_str in stream_answer(query, course_id, conversation_history):
        if not event_str.startswith("data: "):
            continue
        try:
            event = json.loads(event_str[6:])
        except json.JSONDecodeError:
            continue

        if event["type"] == "citations":
            citations = event.get("citations", [])
        elif event["type"] == "token":
            answer_tokens.append(event.get("text", ""))
        elif event["type"] == "error":
            return {
                "answer":           event.get("text", "An error occurred"),
                "citations":        [],
                "chunks_retrieved": 0,
            }

    return {
        "answer":           "".join(answer_tokens),
        "citations":        citations,
        "chunks_retrieved": len(citations),
    }



### FILE MANAGEMENT ###

def list_course_files(course_id: str) -> list[dict]:
    """List all indexed files in a course with metadata."""
    stats = vector_store.get_collection_stats(course_id)
    return stats.get("files", [])


def delete_course_file(course_id: str, file_id: str) -> int:
    """
    Delete all chunks for a file from all three storage layers.
    Returns the number of retrieval chunks deleted.
    """
    # 1. Remove from ChromaDB (retrieval chunks)
    deleted = vector_store.delete_by_file_id(course_id, file_id)

    # 2. Remove from chunk store (context + parent chunks)
    chunk_store.delete_by_file_id(course_id, file_id)

    logger.info(f"Deleted file {file_id} from course {course_id} ({deleted} retrieval chunks)")
    return deleted


def get_course_stats(course_id: str) -> dict:
    """Return collection statistics for a course."""
    return vector_store.get_collection_stats(course_id)


### HELPERS ###

def _save_to_disk(file_bytes: bytes, filename: str, file_id: str) -> None:
    """Save raw PDF to the upload directory for archival."""
    try:
        dest = UPLOAD_DIR / f"{file_id}_{filename}"
        dest.write_bytes(file_bytes)
        logger.debug(f"Saved PDF to {dest}")
    except OSError as e:
        # Non-fatal — indexing can continue even if disk save fails
        logger.warning(f"Could not save PDF to disk: {e}")


def _no_docs_event() -> str:
    """SSE event when no documents are found for the course."""
    import json
    payload = {
        "type": "error",
        "text": (
            "No documents have been indexed for this course yet. "
            "Please upload a PDF first."
        ),
    }
    return f"data: {json.dumps(payload)}\n\n"