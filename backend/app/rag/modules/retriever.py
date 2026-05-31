import logging
import math
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.rag.config import (
    VECTOR_SEARCH_TOP_K,
    BM25_SEARCH_TOP_K,
    HYBRID_SEARCH_WEIGHT_VECTOR,
    HYBRID_SEARCH_WEIGHT_BM25,
    BM25_CACHE_ENABLED,
    SIBLING_CONTEXT_ENABLED,
)
from app.rag.models import RetrievalChunkData, RetrievedResult, ParentChunkData
from app.rag.modules.embedder import embed_single
from app.rag.storage.vector_store import (
    search_vectors,
    fetch_parent,
    fetch_siblings,
)

logger = logging.getLogger(__name__)


### BM25 ###

_bm25_cache: Dict[str, List[Tuple[RetrievalChunkData, List[str]]]] = {}

K1 = 1.5
B  = 0.75


def _tokenize(text: str) -> List[str]:
    return text.lower().split()


def _build_bm25_index(
    db: Session, course_id: str
) -> List[Tuple[RetrievalChunkData, List[str]]]:
    if BM25_CACHE_ENABLED and course_id in _bm25_cache:
        return _bm25_cache[course_id]

    from app.rag.models import RetrievalChunk
    rows = (
        db.query(RetrievalChunk)
        .filter(RetrievalChunk.course_id == course_id)
        .all()
    )

    from app.rag.storage.vector_store import _orm_to_chunk
    index = [
        (_orm_to_chunk(row), _tokenize(row.text))
        for row in rows
    ]

    if BM25_CACHE_ENABLED:
        _bm25_cache[course_id] = index

    return index


def _bm25_score(query_tokens: List[str], doc_tokens: List[str], avg_dl: float) -> float:
    dl   = len(doc_tokens)
    freq = {t: doc_tokens.count(t) for t in set(query_tokens)}
    score = 0.0
    for term, tf in freq.items():
        idf   = math.log(1 + 1 / (1 + doc_tokens.count(term)))
        denom = tf + K1 * (1 - B + B * dl / avg_dl) if avg_dl else 1
        score += idf * (tf * (K1 + 1)) / denom
    return score


def _search_bm25(
    db: Session,
    query: str,
    course_id: str,
    top_k: int = BM25_SEARCH_TOP_K,
) -> List[Tuple[RetrievalChunkData, float]]:
    index        = _build_bm25_index(db, course_id)
    query_tokens = _tokenize(query)
    avg_dl       = sum(len(tokens) for _, tokens in index) / len(index) if index else 1

    scored = [
        (chunk, _bm25_score(query_tokens, tokens, avg_dl))
        for chunk, tokens in index
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def invalidate_bm25_cache(course_id: str) -> None:
    _bm25_cache.pop(course_id, None)


### RRF FUSION ###

def _rrf_fusion(
    result_lists: List[List[Tuple[RetrievalChunkData, float]]],
    k: int = 60,
) -> List[Tuple[RetrievalChunkData, float]]:
    scores: Dict[str, float]          = {}
    chunks: Dict[str, RetrievalChunkData] = {}

    for result_list in result_lists:
        for rank, (chunk, _) in enumerate(result_list):
            cid = chunk.chunk_id
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            chunks[cid] = chunk

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(chunks[cid], score) for cid, score in ranked]


### PARENT + SIBLING FETCH ###

def _enrich_results(
    db: Session,
    rrf_results: List[Tuple[RetrievalChunkData, float]],
    top_k: int,
) -> List[RetrievedResult]:
    results = []

    for chunk, rrf_score in rrf_results[:top_k]:
        parent = fetch_parent(db, chunk.parent_id)

        prev_sibling, next_sibling = None, None
        if SIBLING_CONTEXT_ENABLED:
            prev_sibling, next_sibling = fetch_siblings(
                db, chunk.parent_id, chunk.chunk_index
            )

        results.append(RetrievedResult(
            retrieval_chunk = chunk,
            parent_chunk    = parent,
            combined_score  = rrf_score,
        ))

    return results


### PUBLIC API ###

def retrieve(
    db: Session,
    query: str,
    query_variants: List[str],
    course_id: str,
    top_k: int = VECTOR_SEARCH_TOP_K,
) -> List[RetrievedResult]:
    all_queries = [query] + query_variants
    all_result_lists: List[List[Tuple[RetrievalChunkData, float]]] = []

    for q in all_queries:
        query_embedding = embed_single(q)

        vector_results = search_vectors(db, query_embedding, course_id, top_k)
        bm25_results   = _search_bm25(db, q, course_id, top_k)

        merged = _merge_hybrid(vector_results, bm25_results)
        all_result_lists.append(merged)

    fused = _rrf_fusion(all_result_lists)

    return _enrich_results(db, fused, top_k)


def _merge_hybrid(
    vector_results: List[Tuple[RetrievalChunkData, float]],
    bm25_results:   List[Tuple[RetrievalChunkData, float]],
) -> List[Tuple[RetrievalChunkData, float]]:
    scores: Dict[str, float]              = {}
    chunks: Dict[str, RetrievalChunkData] = {}

    max_v = max((s for _, s in vector_results), default=1.0) or 1.0
    max_b = max((s for _, s in bm25_results),   default=1.0) or 1.0

    for chunk, score in vector_results:
        cid = chunk.chunk_id
        scores[cid] = scores.get(cid, 0.0) + HYBRID_SEARCH_WEIGHT_VECTOR * (score / max_v)
        chunks[cid] = chunk

    for chunk, score in bm25_results:
        cid = chunk.chunk_id
        scores[cid] = scores.get(cid, 0.0) + HYBRID_SEARCH_WEIGHT_BM25 * (score / max_b)
        chunks[cid] = chunk

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(chunks[cid], score) for cid, score in ranked]