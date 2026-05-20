"""
Stores ContextChunks and ParentChunks in per-course JSON files.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Optional

from app.rag.config import CHUNK_STORE_DIR
from app.rag.models import ContextChunk, ParentChunk

logger = logging.getLogger("nexus.rag.chunk_store")

# One lock per course file to prevent concurrent write corruption.
_file_locks: dict[str, threading.Lock] = {}


def _lock_for(course_id: str) -> threading.Lock:
    if course_id not in _file_locks:
        _file_locks[course_id] = threading.Lock()
    return _file_locks[course_id]


def _course_file(course_id: str) -> Path:
    return CHUNK_STORE_DIR / f"{course_id}_chunks.json"


def _load(course_id: str) -> dict:
    """Load the JSON store for a course. Returns empty structure if not found."""
    path = _course_file(course_id)
    if not path.exists():
        return {"contexts": {}, "parents": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load chunk store for {course_id}: {e}")
        return {"contexts": {}, "parents": {}}


def _save(course_id: str, data: dict) -> None:
    """Write the JSON store for a course atomically."""
    path = _course_file(course_id)
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(path)   # Atomic on POSIX; best-effort on Windows
    except OSError as e:
        logger.error(f"Failed to save chunk store for {course_id}: {e}")
        raise


# ── Context chunks ──────────────────────────────────────────────

def save_context_chunks(course_id: str, chunks: dict[str, ContextChunk]) -> None:
    """
    Save a batch of context chunks for a course.
    Merges with any existing data (upsert semantics).
    """
    if not chunks:
        return
    with _lock_for(course_id):
        data = _load(course_id)
        for chunk_id, chunk in chunks.items():
            data["contexts"][chunk_id] = chunk.to_dict()
        _save(course_id, data)
    logger.debug(f"Saved {len(chunks)} context chunks for course {course_id}")


def get_context_chunk(course_id: str, chunk_id: str) -> Optional[ContextChunk]:
    """Retrieve one context chunk by its ID."""
    data = _load(course_id)
    raw = data["contexts"].get(chunk_id)
    if raw is None:
        return None
    return ContextChunk.from_dict(raw)


def get_context_chunks_batch(
    course_id: str, chunk_ids: list[str]
) -> dict[str, ContextChunk]:
    """Retrieve multiple context chunks in one file read."""
    data = _load(course_id)
    result = {}
    for cid in chunk_ids:
        raw = data["contexts"].get(cid)
        if raw:
            result[cid] = ContextChunk.from_dict(raw)
    return result


# ── Parent chunks ───────────────────────────────────────────────

def save_parent_chunks(course_id: str, parents: list[ParentChunk]) -> None:
    """
    Save a list of parent chunks for a course.
    Merges with any existing data (upsert semantics).
    """
    if not parents:
        return
    with _lock_for(course_id):
        data = _load(course_id)
        for parent in parents:
            data["parents"][parent.parent_id] = parent.to_dict()
        _save(course_id, data)
    logger.debug(f"Saved {len(parents)} parent chunks for course {course_id}")


def get_parent_chunk(course_id: str, parent_id: str) -> Optional[ParentChunk]:
    """Retrieve one parent chunk by its ID."""
    data = _load(course_id)
    raw = data["parents"].get(parent_id)
    if raw is None:
        return None
    return ParentChunk.from_dict(raw)


def get_parent_chunks_batch(
    course_id: str, parent_ids: list[str]
) -> dict[str, ParentChunk]:
    """Retrieve multiple parent chunks in one file read."""
    data = _load(course_id)
    result = {}
    for pid in parent_ids:
        raw = data["parents"].get(pid)
        if raw:
            result[pid] = ParentChunk.from_dict(raw)
    return result


# ── Deletion ────────────────────────────────────────────────────

def delete_by_file_id(course_id: str, file_id: str) -> tuple[int, int]:

    with _lock_for(course_id):
        data = _load(course_id)

        # Identify context chunks to remove
        ctx_to_remove = [
            cid for cid, ctx in data["contexts"].items()
            if ctx.get("file_id") == file_id
               or ctx.get("source_filename") == file_id  # fallback
        ]
        for cid in ctx_to_remove:
            del data["contexts"][cid]

        # Identify parent chunks to remove
        par_to_remove = [
            pid for pid, par in data["parents"].items()
            if par.get("file_id") == file_id
               or par.get("source_filename") == file_id
        ]
        for pid in par_to_remove:
            del data["parents"][pid]

        _save(course_id, data)

    logger.info(
        f"Deleted {len(ctx_to_remove)} context + {len(par_to_remove)} parent "
        f"chunks for file_id={file_id} in course {course_id}"
    )
    return len(ctx_to_remove), len(par_to_remove)


def delete_course(course_id: str) -> bool:
    """Delete the entire chunk store for a course."""
    path = _course_file(course_id)
    try:
        if path.exists():
            path.unlink()
        logger.info(f"Deleted chunk store for course {course_id}")
        return True
    except OSError as e:
        logger.error(f"Failed to delete chunk store for {course_id}: {e}")
        return False


def list_files(course_id: str) -> list[dict]:

    data = _load(course_id)
    files: dict[str, dict] = {}
    for ctx in data["contexts"].values():
        fname = ctx.get("source_filename", "unknown")
        if fname not in files:
            files[fname] = {
                "filename":      fname,
                "context_count": 0,
            }
        files[fname]["context_count"] += 1

    return sorted(files.values(), key=lambda f: f["filename"])