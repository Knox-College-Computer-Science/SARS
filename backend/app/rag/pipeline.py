import json
import logging
import time
import uuid
from typing import Dict, Iterator, List, Optional

from app.rag.config import UPLOAD_DIR
from app.rag.models import IndexResult
from app.rag.modules.extractor    import extract_elements, compute_md5, detect_document_type
from app.rag.modules.chunker      import chunk_document
from app.rag.modules.indexer      import index_all
from app.rag.modules.multi_query     import generate_query_variants
from app.rag.modules.retriever    import retrieve_for_query
from app.rag.modules.merger       import merge_results
from app.rag.modules.lookup       import fetch_parents
from app.rag.modules.prompt_builder import build_prompt
from app.rag.modules.generator    import stream_response
from app.rag.storage              import vector_store, chunk_store, eval_store

logger = logging.getLogger("sars.rag.pipeline")


_doc_status: Dict[str, dict] = {}


def get_document_status(file_id: str) -> Optional[dict]:
    """Return current status for a file_id, or None if not found."""
    return _doc_status.get(file_id)


def list_processing_documents(course_id: str) -> List[dict]:
    """Return all documents currently being processed for a course."""
    return [
        v for v in _doc_status.values()
        if v.get("course_id") == course_id and v.get("status") == "processing"
    ]

# INGESTION

def index_document(
    file_bytes: bytes,
    filename:   str,
    course_id:  str,
    user_id:    str = "anonymous",
    file_id:    Optional[str] = None,
) -> IndexResult:
    if file_id is None:
        file_id = str(uuid.uuid4())

    # MD5 duplicate/update detection
    new_hash = compute_md5(file_bytes)
    existing = chunk_store.get_file_metadata(course_id, filename)

    if existing:
        if existing.get("md5_hash") == new_hash:
            # Exact duplicate — same content, skip entirely
            logger.info(f"[INGEST] Duplicate detected: {filename} already indexed for course {course_id}")
            return IndexResult(
                file_id   = existing.get("file_id", file_id),
                filename  = filename,
                course_id = course_id,
                status    = "duplicate",
                error     = "File already indexed (identical content). No changes made.",
            )
        else:
            # Same filename, different content
            old_file_id = existing.get("file_id")
            logger.info(f"[INGEST] Updated file detected: {filename} — removing old chunks")
            if old_file_id:
                vector_store.delete_by_file_id(course_id, old_file_id)
                chunk_store.delete_by_file_id(course_id, old_file_id)

    #  Step 1: Mark as processing
    _doc_status[file_id] = {
        "status":     "processing",
        "filename":   filename,
        "course_id":  course_id,
        "started_at": time.time(),
    }
    logger.info(f"[INGEST] Starting: {filename} → course {course_id} (file_id={file_id})")
    t_start = time.time()

    #  Step 2: Save raw file to disk
    _save_to_disk(file_bytes, filename, file_id)

    #  Step 3: Extract
    try:
        elements = extract_elements(file_bytes, filename)
    except ValueError as e:
        _doc_status[file_id]["status"] = "error"
        return IndexResult(
            file_id=file_id, filename=filename, course_id=course_id,
            status="error", error=str(e),
        )

    if not elements:
        _doc_status[file_id]["status"] = "error"
        return IndexResult(
            file_id=file_id, filename=filename, course_id=course_id,
            status="error",
            error="No content extracted. Is this a scanned image-only PDF? Try enabling OCR.",
        )

    #  Step 4: Detect document type
    doc_type = detect_document_type(elements)
    logger.info(f"[INGEST] Document type: {doc_type} for {filename}")

    # Step 5: Chunk
    parent_chunks, retrieval_chunks = chunk_document(
        elements  = elements,
        filename  = filename,
        file_id   = file_id,
        course_id = course_id,
        user_id   = user_id,
        doc_type  = doc_type,
    )

    # Step 6: Index (embed + store)
    result = index_all(
        retrieval_chunks = retrieval_chunks,
        parent_chunks    = parent_chunks,
        file_id          = file_id,
        filename         = filename,
        course_id        = course_id,
        md5_hash         = new_hash,    #
    )

    result.total_elements = len(elements)

    # Step 7: Update status
    _doc_status[file_id]["status"] = result.status
    _doc_status[file_id]["completed_at"] = time.time()

    elapsed = time.time() - t_start
    logger.info(
        f"[INGEST] Done: {filename} in {elapsed:.1f}s — "
        f"{result.retrieval_chunks} retrieval chunks, "
        f"{result.parent_chunks} parents, status={result.status}"
    )
    return result

# RETRIEVAL + GENERATION

def stream_answer(
    query:                str,
    course_id:            str,
    conversation_history: Optional[List[dict]] = None,
) -> Iterator[str]:
    if conversation_history is None:
        conversation_history = []

    t0 = time.time()

    # 1. Expand query
    variants = generate_query_variants(query)

    # 2. Hybrid search for each variant
    all_raw_results = [
        retrieve_for_query(variant, course_id)
        for variant in variants
    ]

    # 3. Merge + deduplicate
    top_raw = merge_results(all_raw_results)

    retrieval_latency_ms = (time.time() - t0) * 1000

    if not top_raw:
        yield _no_docs_event()
        return

    # 4. Fetch parent chunks
    retrieved = fetch_parents(top_raw, course_id)

    # 5. Log retrieval
    eval_store.log_retrieval(
        query                = query,
        course_id            = course_id,
        query_variants       = variants,
        results              = retrieved,
        retrieval_latency_ms = retrieval_latency_ms,
    )

    # 6. Build prompt
    messages = build_prompt(query, retrieved, conversation_history)

    # 7. Stream answer
    yield from stream_response(messages, retrieved)


def answer_question(
    query:                str,
    course_id:            str,
    conversation_history: Optional[List[dict]] = None,
) -> dict:
    if conversation_history is None:
        conversation_history = []

    answer_tokens: List[str] = []
    citations: List[dict]    = []

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

# FILE MANAGEMENT

def list_course_files(course_id: str) -> List[dict]:
    files = chunk_store.list_files(course_id)

    # Annotate with processing status from in-memory tracker
    for f in files:
        filename = f.get("filename", "")
        processing = [
            v for v in _doc_status.values()
            if v.get("filename") == filename
            and v.get("course_id") == course_id
        ]
        if processing:
            f["status"] = processing[-1].get("status", "indexed")
        else:
            f["status"] = "indexed"

    # Also include files that are still processing (not yet in chunk_store)
    for v in _doc_status.values():
        if v.get("course_id") == course_id and v.get("status") == "processing":
            files.append({
                "filename": v["filename"],
                "status":   "processing",
            })

    return files


def delete_course_file(course_id: str, file_id: str) -> int:
    deleted = vector_store.delete_by_file_id(course_id, file_id)
    chunk_store.delete_by_file_id(course_id, file_id)

    # Clear from status tracker
    _doc_status.pop(file_id, None)

    logger.info(f"Deleted file {file_id} from course {course_id} ({deleted} retrieval chunks)")
    return deleted


def get_course_stats(course_id: str) -> dict:
    """Return collection statistics for a course."""
    return vector_store.get_collection_stats(course_id)

# HELPERS

def _save_to_disk(file_bytes: bytes, filename: str, file_id: str) -> None:
    """Save raw PDF to the upload directory for archival."""
    try:
        dest = UPLOAD_DIR / f"{file_id}_{filename}"
        dest.write_bytes(file_bytes)
        logger.debug(f"Saved PDF to {dest}")
    except OSError as e:
        logger.warning(f"Could not save PDF to disk: {e}")


def _no_docs_event() -> str:
    """SSE event when no documents are found for the course."""
    payload = {
        "type": "error",
        "text": (
            "No documents have been indexed for this course yet. "
            "Please upload a PDF first."
        ),
    }
    return f"data: {json.dumps(payload)}\n\n"