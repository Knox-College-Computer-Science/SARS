
import logging
from typing import List

from app.rag.config import MEMORY_WINDOW
from app.rag.models import RetrievedResult

logger = logging.getLogger("sars.rag.prompt_builder")

SYSTEM_PROMPT = """\
You are SARS AI, a course assistant embedded in a student's course hub.
You answer questions STRICTLY using the retrieved course materials provided below.

Rules:
1. Ground every factual claim in the provided sources.
2. Cite sources inline using [1], [2], etc. immediately after the claim.
3. If a source is a table, read it carefully row by row to find the exact answer.
4. If a source is an image description, note you are referring to a visual.
5. If the answer cannot be found in the provided materials, say clearly:
   "I couldn't find that in the uploaded course materials."
   Do NOT guess or invent information.
6. Be concise but complete. Use markdown formatting where it aids clarity.
7. Do not describe your retrieval process — just answer naturally.\
"""


def build_prompt(
    query:                str,
    results:              List[RetrievedResult],
    conversation_history: List[dict],
) -> List[dict]:

    messages: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    #  Conversation history (sliding window)
    for turn in conversation_history[-MEMORY_WINDOW:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})

    #  Context block
    context_lines: List[str] = ["## Retrieved Course Materials\n"]

    for i, result in enumerate(results, 1):
        rc     = result.retrieval_chunk
        parent = result.parent_chunk

        # Build citation label from retrieval chunk metadata
        section_part = f" — {rc.section_heading}" if rc.section_heading else ""
        citation = f"{rc.source_filename}{section_part}, p.{rc.page_number} ({rc.element_type})"

        # Build metadata header for LLM context
        header_parts = [f"Source: {rc.source_filename}"]
        if rc.section_heading:
            header_parts.append(f"Section: {rc.section_heading}")
        header_parts.append(f"Page: {rc.page_number}")
        header_parts.append(f"Type: {rc.element_type}")
        header = "[" + " | ".join(header_parts) + "]\n\n"

        if rc.element_type == "table" and rc.formatted_content:
            content = f"[Table from {citation}]\n\n{rc.formatted_content}"
        elif parent:
            content = header + parent.text
        else:
            content = header + rc.text

        context_lines.append(f"[{i}] ({citation})")
        context_lines.append(content)
        context_lines.append("")

    context_block = "\n".join(context_lines)

    # Final user message
    user_message = f"{context_block}\n---\n\n**Question:** {query}"
    messages.append({"role": "user", "content": user_message})

    return messages