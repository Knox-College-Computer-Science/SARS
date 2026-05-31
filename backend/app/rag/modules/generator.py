import logging
from typing import AsyncGenerator, List

import google.generativeai as genai

from app.rag.config import (
    GOOGLE_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
)

logger = logging.getLogger(__name__)

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)


### HELPERS ###

def _to_gemini_history(messages: List[dict]) -> List[dict]:
    gemini_messages = []
    for msg in messages:
        role = msg["role"]
        if role == "system":
            continue
        gemini_messages.append({
            "role":  "user" if role == "user" else "model",
            "parts": [msg["content"]],
        })
    return gemini_messages


def _extract_system(messages: List[dict]) -> str:
    for msg in messages:
        if msg["role"] == "system":
            return msg["content"]
    return ""


### PUBLIC API ###

async def stream(messages: List[dict]) -> AsyncGenerator[str, None]:
    if not GOOGLE_API_KEY:
        yield "Error: GOOGLE_API_KEY not configured."
        return

    system_text     = _extract_system(messages)
    history         = _to_gemini_history(messages[:-1])
    user_query      = messages[-1]["content"]

    try:
        model = genai.GenerativeModel(
            model_name   = LLM_MODEL,
            system_instruction = system_text,
            generation_config  = genai.GenerationConfig(
                temperature  = LLM_TEMPERATURE,
                max_output_tokens = LLM_MAX_TOKENS,
            ),
        )

        chat     = model.start_chat(history=history)
        response = await chat.send_message_async(user_query, stream=True)

        async for chunk in response:
            if chunk.text:
                yield chunk.text

    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        yield f"Error: {e}"