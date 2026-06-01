import logging
import re
from typing import List

from app.rag.config import (
    GOOGLE_API_KEY,
    LLM_MODEL,
    QUERY_VARIANTS_COUNT,
    MULTIQUERY_ENABLED,
)

logger = logging.getLogger(__name__)


_TABLE_KEYWORDS = {
    "table", "row", "column", "value", "rate", "percentage",
    "price", "cost", "score", "grade", "list", "when", "date",
    "how many", "how much", "what is the", "what are the",
}

_CONCEPTUAL_KEYWORDS = {
    "explain", "why", "how does", "what is", "describe",
    "difference between", "compare", "relationship", "define",
}

_PLANNING_KEYWORDS = {
    "prerequisite", "before", "requirement", "sequence",
    "schedule", "plan", "next", "after",
}

_SYLLABUS_KEYWORDS = {
    "syllabus", "exam", "quiz", "deadline", "due", "policy",
    "grading", "office hours", "professor", "instructor",
}


def detect_intent(query: str) -> str:
    q = query.lower()
    if any(kw in q for kw in _SYLLABUS_KEYWORDS):
        return "syllabus"
    if any(kw in q for kw in _TABLE_KEYWORDS):
        return "table_lookup"
    if any(kw in q for kw in _PLANNING_KEYWORDS):
        return "planning"
    if any(kw in q for kw in _CONCEPTUAL_KEYWORDS):
        return "conceptual"
    return "factual"


_EXPANSION_PROMPT = """You are a query expansion assistant for a university course RAG system.

Given a student's question, generate {n} alternative phrasings that:
1. Rephrase using different vocabulary a textbook might use
2. Extract the core keyword terms only (for keyword search)

Return ONLY the alternative questions, one per line, no numbering, no explanation.

Student question: {query}"""


def expand_query(query: str) -> List[str]:
    if not MULTIQUERY_ENABLED:
        return []

    if not GOOGLE_API_KEY:
        logger.warning("No GOOGLE_API_KEY — multi-query expansion disabled")
        return _fallback_expansion(query)

    try:
        from google import genai
        client   = genai.Client(api_key=GOOGLE_API_KEY)
        prompt   = _EXPANSION_PROMPT.format(
            n=QUERY_VARIANTS_COUNT - 1,
            query=query,
        )
        response = client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt,
        )
        lines = [
            line.strip()
            for line in response.text.strip().splitlines()
            if line.strip() and line.strip() != query
        ]
        variants = lines[: QUERY_VARIANTS_COUNT - 1]
        logger.info(f"Expanded query into {len(variants)} variants")
        return variants

    except Exception as e:
        logger.warning(f"Query expansion failed: {e}, using fallback")
        return _fallback_expansion(query)


def _fallback_expansion(query: str) -> List[str]:
    words           = query.lower().split()
    keywords        = [w for w in words if len(w) > 3]
    keyword_variant = " ".join(keywords) if keywords else query
    return [keyword_variant] if keyword_variant != query else []