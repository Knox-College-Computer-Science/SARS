import logging
from typing import List

from app.rag.config import RERANK_TOP_K, RERANKING_ENABLED
from app.rag.models import RetrievedResult

logger = logging.getLogger(__name__)


async def rerank(
    query: str,
    results: List[RetrievedResult],
    top_k: int = RERANK_TOP_K,
) -> List[RetrievedResult]:
    return results[:top_k]


def assess_confidence(results: List[RetrievedResult]) -> str:
    if not results:
        return "none"

    top_score = (
        results[0].rerank_score
        if results[0].rerank_score
        else results[0].combined_score
    )

    if top_score >= 0.7:
        return "high"
    elif top_score >= 0.4:
        return "medium"
    return "low"