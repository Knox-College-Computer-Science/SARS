### Multi-Query ###

import logging
import re

import ollama as _ollama

from app.rag.config import (
    LLM_MODEL,
    MULTIQUERY_ENABLED,
    MULTIQUERY_VARIANTS,
    MULTIQUERY_PROMPT_TEMPLATE,
)

logger = logging.getLogger("nexus.rag.expander")


def generate_query_variants(query: str) -> list[str]:

    if not MULTIQUERY_ENABLED:
        return [query]

    try:
        alternatives = _generate_alternatives(query, MULTIQUERY_VARIANTS)
        variants = [query] + alternatives
        logger.debug(f"Query expanded to {len(variants)} variants: {variants}")
        return variants
    except Exception as e:
        logger.warning(f"Multi-query generation failed, using original query: {e}")
        return [query]


def _generate_alternatives(query: str, n: int) -> list[str]:

    prompt = MULTIQUERY_PROMPT_TEMPLATE.format(n=n, query=query)

    response = _ollama.generate(
        model=LLM_MODEL,
        prompt=prompt,

        options={"num_predict": 120, "temperature": 0.3},
    )
    raw = response.get("response", "").strip()

    alternatives = _parse_alternatives(raw, n)
    return alternatives


def _parse_alternatives(raw: str, n: int) -> list[str]:

    lines = raw.split("\n")
    alternatives = []

    for line in lines:
        # Strip leading numbers, bullets, dashes, dots
        cleaned = re.sub(r"^[\d\.\-\*\)\s]+", "", line).strip()
        # Skip empty lines or lines that are clearly metadata
        if cleaned and len(cleaned) > 5:
            alternatives.append(cleaned)

    # Take exactly n alternatives (pad with original trimmed variants if short)
    return alternatives[:n]