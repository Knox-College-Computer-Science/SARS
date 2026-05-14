
import logging
from typing import Optional

from app.rag.config import MEMORY_WINDOW
from app.rag.models import RetrievedResult

logger = logging.getLogger("nexus.rag.prompt_builder")

# If a context chunk is shorter than this, use the parent text instead.
# Parent text is richer but may contain off-topic content from the section.
_SHORT_CHUNK_THRESHOLD = 150  # chars

SYSTEM_PROMPT = """\
You are Nexus AI, a course assistant embedded in a student's course hub.
You answer questions STRICTLY using the retrieved course materials provided below.

Rules:
1. Ground every factual claim in the provided sources.
2. Cite sources inline using [1], [2], etc. immediately after the claim.
3. If a source is a table, interpret the data accurately and cite the table number.
4. If a source is an image description, note you are referring to a visual.
5. If the answer cannot be found in the provided materials, say clearly:
   "I couldn't find that in the uploaded course materials."
   Do NOT guess or invent information.
6. Be concise but complete. Use markdown formatting where it aids clarity.
7. Do not describe your retrieval process — just answer naturally.\
"""


def build_prompt(
    query:                str,
    results:              list[RetrievedResult],
    conversation_history: list[dict],
) -> list[dict]:

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # ── Conversation history (sliding window) ────────────────────
    for turn in conversation_history[-MEMORY_WINDOW:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})

    # ── Context block ────────────────────────────────────────────
    context_lines: list[str] = ["## Retrieved Course Materials\n"]

    for i, result in enumerate(results, 1):
        citation = result.citation_label
        rc       = result.retrieval_chunk

        # Choose the content the LLM should read:
        #  - For tables: use markdown (formatted_content)
        #  - For short chunks: use parent text (richer context)
        #  - Otherwise: use context chunk text (header + retrieval text)
        if rc.element_type == "table" and rc.formatted_content:
            content = _table_content(rc.formatted_content, citation)

        elif (
            result.context_chunk
            and len(result.context_chunk.text) < _SHORT_CHUNK_THRESHOLD
            and result.parent_chunk
        ):
            # Chunk is very short — send the full parent section instead
            content = result.parent_chunk.text
            logger.debug(f"Using parent text for short chunk [{i}]")

        elif result.context_chunk:
            content = result.context_chunk.text   # Header + chunk text

        else:
            # Fallback: just the raw retrieval text
            content = rc.text

        context_lines.append(f"[{i}] ({citation})")
        context_lines.append(content)
        context_lines.append("")   # Blank line between sources

    context_block = "\n".join(context_lines)

    # ── Final user message ───────────────────────────────────────
    user_message = f"{context_block}\n---\n\n**Question:** {query}"
    messages.append({"role": "user", "content": user_message})

    return messages


def _table_content(markdown: str, citation: str) -> str:
    """
    Format a table for the LLM. Adds a note that this is a table
    so the LLM treats it structurally rather than as prose.
    """
    return f"[This source is a data table from {citation}]\n\n{markdown}"