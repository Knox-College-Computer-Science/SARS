import logging
from typing import AsyncGenerator, List

from app.rag.config import (
    GOOGLE_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
)

logger = logging.getLogger(__name__)


def _to_gemini_history(messages: List[dict]) -> List[dict]:
    gemini_messages = []
    for msg in messages:
        role = msg["role"]
        if role == "system":
            continue
        gemini_messages.append({
            "role":  "user" if role == "user" else "model",
            "parts": [{"text": msg["content"]}],
        })
    return gemini_messages


def _extract_system(messages: List[dict]) -> str:
    for msg in messages:
        if msg["role"] == "system":
            return msg["content"]
    return ""


async def stream(messages: List[dict]) -> AsyncGenerator[str, None]:
    if not GOOGLE_API_KEY:
        yield "Error: GOOGLE_API_KEY not configured."
        return

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GOOGLE_API_KEY)

    system_text = _extract_system(messages)
    history     = _to_gemini_history(messages[:-1])
    user_query  = messages[-1]["content"]

    contents = history + [{"role": "user", "parts": [{"text": user_query}]}]

    try:
        response = client.aio.models.generate_content_stream(
            model=LLM_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_text,
                temperature=LLM_TEMPERATURE,
                max_output_tokens=LLM_MAX_TOKENS,
            ),
        )
        async for chunk in await response:
            if chunk.text:
                yield chunk.text

    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            yield "The AI service is temporarily unavailable due to rate limits. Please try again in a minute."
        else:
            logger.error(f"Generation failed: {e}", exc_info=True)
            yield f"Error: {e}"