"""
Takes results from multiple hybrid searches (one per query variant)
and produces a single deduplicated, ranked list.

"""

import logging
from app.rag.config import TOP_K_FINAL
from app.rag.models import RetrievedResult, RetrievalChunk

logger = logging.getLogger("nexus.rag.merger")

_RRF_K = 60   # Standard RRF constant


def merge_results(
    all_results: list[list[dict]],
    top_k: int = TOP_K_FINAL,
) -> list[dict]:
    """
    Merge result lists from multiple query variants into one ranked list.
    """
    if not all_results:
        return []

    # Flatten with rank information for RRF
    chunk_data:    dict[str, dict]  = {}   # chunk_id → best result dict
    chunk_rrf:     dict[str, float] = {}   # chunk_id → accumulated RRF score

    for result_list in all_results:
        for rank, result in enumerate(result_list, start=1):
            cid = result["chunk_id"]

            # RRF contribution from this list
            rrf_contribution = 1.0 / (_RRF_K + rank)
            chunk_rrf[cid] = chunk_rrf.get(cid, 0.0) + rrf_contribution

            # Keep the highest combined_score occurrence
            existing = chunk_data.get(cid)
            if existing is None or result["combined_score"] > existing["combined_score"]:
                chunk_data[cid] = result

    # Build final ranked list
    final: list[dict] = []
    for cid, data in chunk_data.items():
        rrf_score   = chunk_rrf[cid]
        # Normalise RRF (max possible per list = 1/61 ≈ 0.016)
        # We just use it as a tiebreaker blend, not strict normalisation
        final_score = 0.7 * data["combined_score"] + 0.3 * min(rrf_score * 10, 1.0)
        final.append({
            **data,
            "rrf_score":   round(rrf_score, 4),
            "final_score": round(final_score, 4),
        })

    final.sort(key=lambda x: x["final_score"], reverse=True)
    top = final[:top_k]

    logger.debug(
        f"Merged {sum(len(r) for r in all_results)} results "
        f"from {len(all_results)} variants → {len(top)} final"
    )
    return top