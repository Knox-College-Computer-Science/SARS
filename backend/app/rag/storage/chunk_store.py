"""
storage/chunk_store.py — Parent Chunk Store
============================================

Stores ParentChunks and file metadata in per-course JSON files.
ChromaDB holds the retrieval chunks (with embeddings).
This store holds full section text for LLM context.

CHANGE FROM ORIGINAL:
  - ContextChunk tier removed (no save_context_chunks, get_context_chunks_batch)
  - Added "files" section for MD5-based duplicate detection
  - Added save_file_metadata() and get_file_metadata()
  - list_files() now derived from "files" section (not "contexts")

FILE LAYOUT:
  rag_storage/chunk_store/
    course_1_chunks.json
    course_2_chunks.json
    ...

Each file structure:
  {
    "parents": { parent_id: ParentChunk.to_dict(), ... },
    "files":   { filename:  { file_id, filename, md5_hash, course_id }, ... }
  }

UPGRADE PATH TO SUPABASE:
  Replace _load()/_save() with Supabase queries.
  Public function signatures stay identical.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.rag.config import CHUNK_STORE_DIR
from app.rag.models import ParentChunk

logger = logging.getLogger("sars.rag.chunk_store")

# One lock per course file to prevent concurrent write corruption.
_file_locks: Dict[str, threading.Lock] = {}


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
        return {"parents": {}, "files": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Backwards compatibility: add "files" key if missing
            if "files" not in data:
                data["files"] = {}
            return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load chunk store for {course_id}: {e}")
        return {"parents": {}, "files": {}}


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


# ── Parent chunks ───────────────────────────────────────────────

def save_parent_chunks(course_id: str, parents: List[ParentChunk]) -> None:
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
    course_id: str, parent_ids: List[str]
) -> Dict[str, ParentChunk]:
    """Retrieve multiple parent chunks in one file read."""
    data = _load(course_id)
    result = {}
    for pid in parent_ids:
        raw = data["parents"].get(pid)
        if raw:
            result[pid] = ParentChunk.from_dict(raw)
    return result


# ── File metadata (MD5 duplicate detection) ─────────────────────

def save_file_metadata(course_id: str, metadata: dict) -> None:
    """
    Store file metadata keyed by filename.

    metadata must include: file_id, filename, md5_hash, course_id

    Used by pipeline.index_document() to detect:
      - Exact duplicates (same MD5 → skip)
      - Updated files (same filename, different MD5 → replace old chunks)
    """
    filename = metadata.get("filename", "")
    if not filename:
        return
    with _lock_for(course_id):
        data = _load(course_id)
        data["files"][filename] = metadata
        _save(course_id, data)
    logger.debug(f"Saved file metadata for {filename} in course {course_id}")


def get_file_metadata(course_id: str, filename: str) -> Optional[dict]:
    """
    Return stored metadata for a filename, or None if not found.
    Used to check for duplicates before indexing.
    """
    data = _load(course_id)
    return data["files"].get(filename)


# ── Deletion ────────────────────────────────────────────────────

def delete_by_file_id(course_id: str, file_id: str) -> int:
    """
    Remove all parent chunks and file metadata belonging to a file_id.
    Returns count of parent chunks deleted.
    """
    with _lock_for(course_id):
        data = _load(course_id)

        # Remove parent chunks
        to_remove = [
            pid for pid, par in data["parents"].items()
            if par.get("file_id") == file_id
        ]
        for pid in to_remove:
            del data["parents"][pid]

        # Remove file metadata entry
        files_to_remove = [
            fname for fname, meta in data["files"].items()
            if meta.get("file_id") == file_id
        ]
        for fname in files_to_remove:
            del data["files"][fname]

        _save(course_id, data)

    logger.info(
        f"Deleted {len(to_remove)} parent chunks for file_id={file_id} "
        f"in course {course_id}"
    )
    return len(to_remove)


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


# ── List files ───────────────────────────────────────────────────

def list_files(course_id: str) -> List[dict]:
    """
    Return a list of all files indexed for a course.
    Derived from the "files" metadata section.
    """
    data = _load(course_id)
    files = []
    for fname, meta in data["files"].items():
        files.append({
            "filename": fname,
            "file_id":  meta.get("file_id", ""),
        })
    return sorted(files, key=lambda f: f["filename"])