import json
import logging
from typing import Iterator

import ollama as _ollama

from app.rag.config import LLM_MODEL
from app.rag.models import RetrievedResult

logger = logging.getLogger("nexus.rag.generator")


def stream_response(
    prompt_messages: list[dict],
    results:         list[RetrievedResult],
) -> Iterator[str]:
    """
    Stream an LLM answer as SSE events.

    """
    # ── Emit citations immediately (before LLM starts) ───────────
    citations = _build_citations_payload(results)
    yield _sse("citations", {"citations": citations})

    # ── Stream tokens from Ollama ─────────────────────────────────
    try:
        stream = _ollama.chat(
            model    = LLM_MODEL,
            messages = prompt_messages,
            stream   = True,
        )

        for chunk in stream:
            token = chunk.get("message", {}).get("content", "")
            if token:
                yield _sse("token", {"text": token})

    except Exception as e:
        logger.error(f"LLM streaming failed: {e}", exc_info=True)
        yield _sse("error", {"text": f"Generation error: {e}"})
        return

    yield _sse("done", {})


def _build_citations_payload(results: list[RetrievedResult]) -> list[dict]:
    """
    Build the citations list sent to the frontend in the first SSE event.

    """
    citations = []
    for i, result in enumerate(results, 1):
        rc = result.retrieval_chunk
        citations.append({
            "index":        i,
            "source":       rc.source_filename,
            "section":      rc.section_heading,
            "page":         rc.page_number,
            "element_type": rc.element_type,
            "relevance":    round(result.combined_score, 3),
            "citation":     result.citation_label,
        })
    return citations


def _sse(event_type: str, data: dict) -> str:
    """Format a dict as an SSE data event string."""
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"