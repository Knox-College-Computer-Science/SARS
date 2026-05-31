import logging
from typing import List, Tuple

from app.rag.config import (
    RETRIEVAL_MAX_TOKENS,
    RERANK_TOP_K,
)
from app.rag.models import RetrievedResult

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4


### HELPERS ###

def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _format_chunk(result: RetrievedResult) -> str:
    c = result.retrieval_chunk

    if c.element_type == "table":
        content = c.formatted_content or c.text
        return f"[Table | {c.source_filename} p.{c.page_number}]\n{content}"

    if c.element_type == "image":
        return f"[Image | {c.source_filename} p.{c.page_number}]\n{c.text}"

    if result.parent_chunk:
        return (
            f"[{c.source_filename} | {c.section_heading} | p.{c.page_number}]\n"
            f"{result.parent_chunk.text}"
        )

    return (
        f"[{c.source_filename} | {c.section_heading} | p.{c.page_number}]\n"
        f"{c.text}"
    )


### PUBLIC API ###

def pack(
    results: List[RetrievedResult],
    budget: int = RETRIEVAL_MAX_TOKENS,
) -> Tuple[str, List[RetrievedResult]]:
    if not results:
        return "", []

    selected: List[RetrievedResult] = []
    used_tokens = 0
    seen_parents = set()

    for result in results:
        c = result.retrieval_chunk

        if c.element_type in ("table", "image"):
            display_text = _format_chunk(result)
        elif result.parent_chunk and result.parent_chunk.parent_id not in seen_parents:
            display_text = _format_chunk(result)
            seen_parents.add(result.parent_chunk.parent_id)
        else:
            result_copy = RetrievedResult(
                retrieval_chunk = result.retrieval_chunk,
                parent_chunk    = None,
                combined_score  = result.combined_score,
                rerank_score    = result.rerank_score,
            )
            display_text = _format_chunk(result_copy)

        tokens = _estimate_tokens(display_text)
        if used_tokens + tokens > budget:
            logger.info(
                f"Context budget reached at {used_tokens} tokens "
                f"({len(selected)} chunks selected)"
            )
            break

        used_tokens += tokens
        selected.append(result)

    context_block = "\n\n---\n\n".join(_format_chunk(r) for r in selected)

    logger.info(
        f"Packed {len(selected)}/{len(results)} chunks "
        f"into ~{used_tokens} tokens"
    )
    return context_block, selected