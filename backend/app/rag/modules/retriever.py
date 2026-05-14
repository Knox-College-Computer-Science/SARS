"""
 Hybrid Search

"""

import logging
from typing import Optional

from app.rag.config import (
    TOP_K_VECTOR,
    TOP_K_BM25,
    VECTOR_WEIGHT,
    BM25_WEIGHT,
)
from app.rag.models import RetrievalChunk
from app.rag.modules.embedder import embed_single
from app.rag.storage.vector_store import query_collection, get_all_documents

logger = logging.getLogger("nexus.rag.retriever")


def retrieve_for_query(
    query: str,
    course_id: str,
    n_vector: int = TOP_K_VECTOR,
    n_bm25:   int = TOP_K_BM25,
) -> list[dict]:
    """
    Run hybrid search for a single query string.

    """
    # ── Vector search ────────────────────────────────────────────
    vector_results = _vector_search(query, course_id, n_vector)

    # ── BM25 search ──────────────────────────────────────────────
    bm25_results = _bm25_search(query, course_id, n_bm25)

    # ── Merge ────────────────────────────────────────────────────
    merged = _merge(vector_results, bm25_results)

    return merged


# ── Vector search ────────────────────────────────────────────────

def _vector_search(
    query: str,
    course_id: str,
    n: int,
) -> list[dict]:
    """
    Embed query and search ChromaDB. Returns normalised results.
    """
    try:
        query_embedding = embed_single(query)
    except RuntimeError as e:
        logger.error(f"Cannot embed query: {e}")
        return []

    raw = query_collection(course_id, query_embedding, n_results=n)

    # Scores are already in (0,1] from vector_store.query_collection
    return [
        {
            "chunk_id":     r["id"],
            "document":     r["document"],
            "metadata":     r["metadata"],
            "vector_score": r["score"],
            "bm25_score":   0.0,
        }
        for r in raw
    ]


# ── BM25 search ──────────────────────────────────────────────────

def _bm25_search(
    query: str,
    course_id: str,
    n: int,
) -> list[dict]:
    """
    BM25 keyword search over all stored documents for the course.

    """
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        logger.warning(
            "rank_bm25 not installed — BM25 search disabled. "
            "Install with: pip install rank-bm25"
        )
        return []

    all_docs = get_all_documents(course_id)
    if not all_docs:
        return []

    # Tokenise (simple whitespace split — sufficient for BM25)
    tokenised = [doc["document"].lower().split() for doc in all_docs]
    bm25      = BM25Okapi(tokenised)

    # Score all documents against the query
    query_tokens = query.lower().split()
    scores       = bm25.get_scores(query_tokens)

    # Normalise to [0, 1]
    max_score = max(scores) if scores.any() else 1.0
    if max_score == 0:
        return []
    norm_scores = scores / max_score

    # Collect top-n results with score > 0
    indexed = sorted(
        [(i, float(norm_scores[i])) for i in range(len(all_docs)) if norm_scores[i] > 0],
        key=lambda x: x[1],
        reverse=True,
    )[:n]

    return [
        {
            "chunk_id":     all_docs[i]["id"],
            "document":     all_docs[i]["document"],
            "metadata":     all_docs[i]["metadata"],
            "vector_score": 0.0,
            "bm25_score":   score,
        }
        for i, score in indexed
    ]


# ── Score merging ────────────────────────────────────────────────

def _merge(
    vector_results: list[dict],
    bm25_results:   list[dict],
) -> list[dict]:
    """
    Merge vector and BM25 results into a single ranked list.

    """
    combined: dict[str, dict] = {}

    for r in vector_results:
        cid = r["chunk_id"]
        combined[cid] = {
            **r,
            "combined_score": VECTOR_WEIGHT * r["vector_score"],
        }

    for r in bm25_results:
        cid = r["chunk_id"]
        if cid in combined:
            # Already in vector results — add BM25 contribution
            combined[cid]["bm25_score"]    = r["bm25_score"]
            combined[cid]["combined_score"] += BM25_WEIGHT * r["bm25_score"]
        else:
            # Only in BM25 results
            combined[cid] = {
                **r,
                "combined_score": BM25_WEIGHT * r["bm25_score"],
            }

    return sorted(combined.values(), key=lambda x: x["combined_score"], reverse=True)