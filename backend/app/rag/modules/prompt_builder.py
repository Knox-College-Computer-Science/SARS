import logging
from typing import List

from app.rag.config import HISTORY_MAX_TOKENS, RETRIEVAL_MEMORY_WINDOW

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4


### SYSTEM PROMPTS ###

_BASE_SYSTEM = """You are SARS AI, a course assistant for {course_name}.

Your job is to answer student questions using only the provided course materials.

Rules:
- Only use information from the retrieved materials below
- If the answer is not in the materials, say so clearly — do not guess
- Cite sources inline using the format [filename, p.N]
- Be concise and direct"""

_CONFIDENCE_INSTRUCTIONS = {
    "high":   "",
    "medium": "\nNote: Retrieval confidence is moderate. Mention if you are uncertain about any specific detail.",
    "low":    "\nNote: Retrieval confidence is low. Clearly state that the materials may not fully address this question.",
    "none":   "\nNote: No relevant materials were found. Tell the student you could not find an answer in the course materials.",
}

_INTENT_INSTRUCTIONS = {
    "table_lookup": "\nFor this query: Read any tables row by row to find exact values. Quote the exact figure.",
    "conceptual":   "\nFor this query: Provide a thorough explanation with examples from the materials.",
    "factual":      "\nFor this query: Give a direct, specific answer with the exact source cited.",
    "planning":     "\nFor this query: Consider any prerequisites or sequences mentioned in the materials.",
    "syllabus":     "\nFor this query: Look for exact dates, policies, or grading information in the materials.",
}


### HISTORY TRIMMING ###

def _trim_history(history: List[dict]) -> List[dict]:
    if not history:
        return []

    trimmed = history[-RETRIEVAL_MEMORY_WINDOW:]
    total_chars = sum(len(m.get("content", "")) for m in trimmed)
    max_chars   = HISTORY_MAX_TOKENS * CHARS_PER_TOKEN

    while trimmed and total_chars > max_chars:
        removed     = trimmed.pop(0)
        total_chars -= len(removed.get("content", ""))

    return trimmed


### PUBLIC API ###

def build_messages(
    query: str,
    context_block: str,
    history: List[dict],
    course_name: str,
    confidence: str = "high",
    intent: str = "factual",
) -> List[dict]:
    system_text = _BASE_SYSTEM.format(course_name=course_name)
    system_text += _CONFIDENCE_INSTRUCTIONS.get(confidence, "")
    system_text += _INTENT_INSTRUCTIONS.get(intent, "")

    if context_block:
        system_text += f"\n\n### RETRIEVED MATERIALS ###\n\n{context_block}"
    else:
        system_text += "\n\n### RETRIEVED MATERIALS ###\n\nNo relevant materials found."

    trimmed_history = _trim_history(history)

    messages = [{"role": "system", "content": system_text}]
    messages.extend(trimmed_history)
    messages.append({"role": "user", "content": query})

    total_chars = sum(len(m["content"]) for m in messages)
    logger.info(
        f"Built prompt: {len(messages)} messages, "
        f"~{total_chars // CHARS_PER_TOKEN} tokens "
        f"(confidence={confidence}, intent={intent})"
    )

    return messages