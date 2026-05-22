import re
import hashlib
import logging
from typing import Optional

import chromadb
from chromadb.config import Settings

from app.rag.config import CHROMA_DIR, COLLECTION_PREFIX, TOP_K_VECTOR

logger = logging.getLogger("nexus.rag.vector_store")


# ── Singletons ──────────────────────────────────────────────────
# One ChromaDB client shared across the process.
# Collections are created on first access and cached.

_client: Optional[chromadb.PersistentClient] = None
_collections: dict[str, chromadb.Collection] = {}


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        logger.info(f"ChromaDB client initialised at {CHROMA_DIR}")
    return _client


def _collection_name(course_id: str) -> str:

    sanitised = re.sub(r"[^a-zA-Z0-9_-]", "_", course_id).strip("_-")
    name = f"{COLLECTION_PREFIX}{sanitised}"

    if len(name) < 3:
        name = name + "_col"

    if len(name) > 63:
        hashed = hashlib.md5(course_id.encode()).hexdigest()[:16]
        name = f"{COLLECTION_PREFIX}{hashed}"

    return name


def get_course_collection(course_id: str) -> chromadb.Collection:

    if course_id not in _collections:
        client = _get_client()
        name = _collection_name(course_id)
        _collections[course_id] = client.get_or_create_collection(
            name=name,
            metadata={"course_id": course_id},
        )
        logger.debug(f"Collection ready: {name}")
    return _collections[course_id]


# ── Write operations ────────────────────────────────────────────

def upsert_chunks(
    course_id: str,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:

    if not ids:
        return
    collection = get_course_collection(course_id)
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    logger.debug(f"Upserted {len(ids)} chunks into course {course_id}")


def delete_by_file_id(course_id: str, file_id: str) -> int:

    collection = get_course_collection(course_id)
    if collection.count() == 0:
        return 0

    all_data = collection.get(include=["metadatas"])
    ids_to_delete = [
        all_data["ids"][i]
        for i, meta in enumerate(all_data["metadatas"])
        if meta.get("file_id") == file_id
    ]

    if ids_to_delete:
        collection.delete(ids=ids_to_delete)
        logger.info(f"Deleted {len(ids_to_delete)} chunks for file_id={file_id}")

    return len(ids_to_delete)


def delete_course(course_id: str) -> bool:
    """Delete the entire collection for a course."""
    try:
        client = _get_client()
        name = _collection_name(course_id)
        client.delete_collection(name)
        _collections.pop(course_id, None)
        logger.info(f"Deleted collection for course {course_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete collection for course {course_id}: {e}")
        return False


# ── Read operations ─────────────────────────────────────────────

def query_collection(
    course_id: str,
    query_embedding: list[float],
    n_results: int = TOP_K_VECTOR,
) -> list[dict]:

    collection = get_course_collection(course_id)
    count = collection.count()
    if count == 0:
        return []

    actual_n = min(n_results, count)
    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_n,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.error(f"ChromaDB query failed for course {course_id}: {e}")
        return []

    output = []
    docs      = results["documents"][0]
    metas     = results["metadatas"][0]
    distances = results["distances"][0]
    ids       = results["ids"][0]

    for i in range(len(docs)):
        distance = distances[i]
        # Convert L2 distance to a similarity score in (0, 1]
        score = 1.0 / (1.0 + distance)
        output.append({
            "id":       ids[i],
            "document": docs[i],
            "metadata": metas[i],
            "distance": distance,
            "score":    score,
        })

    return output


def get_all_documents(course_id: str) -> list[dict]:

    collection = get_course_collection(course_id)
    if collection.count() == 0:
        return []

    all_data = collection.get(include=["documents", "metadatas"])
    output = []
    for i, doc in enumerate(all_data["documents"]):
        output.append({
            "id":       all_data["ids"][i],
            "document": doc,
            "metadata": all_data["metadatas"][i],
        })
    return output


def get_collection_stats(course_id: str) -> dict:
    """Return basic stats about a course's collection."""
    collection = get_course_collection(course_id)
    count = collection.count()
    if count == 0:
        return {"course_id": course_id, "total_chunks": 0}

    all_data = collection.get(include=["metadatas"])

    files: dict[str, dict] = {}
    for meta in all_data["metadatas"]:
        fname = meta.get("source_filename", "unknown")
        if fname not in files:
            files[fname] = {
                "filename":      fname,
                "file_id":       meta.get("file_id", ""),
                "chunk_count":   0,
                "element_types": set(),
            }
        files[fname]["chunk_count"] += 1
        files[fname]["element_types"].add(meta.get("element_type", "text"))

    file_list = []
    for info in files.values():
        info["element_types"] = sorted(info["element_types"])
        file_list.append(info)

    return {
        "course_id":   course_id,
        "total_chunks": count,
        "total_files":  len(file_list),
        "files":        sorted(file_list, key=lambda f: f["filename"]),
    }