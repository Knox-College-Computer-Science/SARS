import json
import logging
from typing import List

import google.generativeai as genai

from app.rag.config import RERANK_TOP_K, RERANKING_ENABLED
from app.rag.models import RetrievedResult

logger = logging.getLogger(__name__)


### PUBLIC API ###

async def rerank(
    query: str,
    results: List[RetrievedResult],
    top_k: int = RERANK_TOP_K,
) -> List[RetrievedResult]:
    if not RERANKING_ENABLED or not results:
        return results[:top_k]

    if len(results) == 1:
        return results

    passages = [r.retrieval_chunk.text[:400] for r in results]

    prompt = (
        f"Query: {query}\n\n"
        f"Passages (indexed 0 to {len(passages) - 1}):\n"
        + "\n".join(f"[{i}] {p}" for i, p in enumerate(passages))
        + "\n\nRank these passages by relevance to the query. "
        "Return ONLY a JSON array of indices, most relevant first. "
        f"Example for 4 passages: [2, 0, 3, 1]"
    )

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = await model.generate_content_async(prompt)
        raw = response.text.strip()

        # strip markdown fences if Gemini wraps the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        indices = json.loads(raw)

        # validate: must be a permutation of valid indices
        valid = set(range(len(results)))
        indices = [i for i in indices if i in valid]

        # append any missing indices at the end (safety net)
        seen = set(indices)
        indices += [i for i in range(len(results)) if i not in seen]

        reranked = [results[i] for i in indices]

        logger.info(f"Gemini reranked {len(results)} → returning top {top_k}")
        return reranked[:top_k]

    except Exception as e:
        logger.warning(f"Gemini reranking failed ({e}), falling back to original order")
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