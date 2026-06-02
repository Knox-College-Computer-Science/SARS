import json
import logging
from typing import AsyncGenerator, List

import httpx

from app.rag.config import (
    GOOGLE_API_KEY,
    GROQ_API_KEY,
    OPENROUTER_API_KEY,
    LLM_PROVIDER,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
)

logger = logging.getLogger(__name__)


### Helpers ###

def _extract_system(messages: List[dict]) -> str:
    for msg in messages:
        if msg["role"] == "system":
            return msg["content"]
    return ""


def _to_openai_messages(messages: List[dict]) -> List[dict]:
    return [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m["role"] in ("system", "user", "assistant")
    ]


def _to_gemini_history(messages: List[dict]) -> List[dict]:
    result = []
    for msg in messages:
        if msg["role"] == "system":
            continue
        result.append({
            "role":  "user" if msg["role"] == "user" else "model",
            "parts": [{"text": msg["content"]}],
        })
    return result

async def _stream_openai_compatible(
    messages: List[dict],
    api_key: str,
    base_url: str,
    model: str,
    provider_name: str,
) -> AsyncGenerator[str, None]:
    if not api_key:
        yield f"Error: API key for {provider_name} not configured."
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model":       model,
        "messages":    _to_openai_messages(messages),
        "temperature": LLM_TEMPERATURE,
        "max_tokens":  LLM_MAX_TOKENS,
        "stream":      True,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                headers=headers,
                json=body,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        event = json.loads(payload)
                        delta = event["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    except httpx.HTTPStatusError as e:
        if "429" in str(e):
            yield f"Rate limit reached on {provider_name}. Please try again shortly."
        elif "413" in str(e):
            yield "The document context is too large to process in one request. Try asking a more specific question."
        else:
            logger.error(f"{provider_name} HTTP error: {e}", exc_info=True)
            yield f"Error from {provider_name}: {e}"
    except Exception as e:
        logger.error(f"{provider_name} generation failed: {e}", exc_info=True)
        yield f"Error: {e}"


async def _stream_groq(messages: List[dict]) -> AsyncGenerator[str, None]:
    async for token in _stream_openai_compatible(
        messages      = messages,
        api_key       = GROQ_API_KEY,
        base_url      = "https://api.groq.com/openai/v1",
        model         = LLM_MODEL,
        provider_name = "Groq",
    ):
        yield token


async def _stream_openrouter(messages: List[dict]) -> AsyncGenerator[str, None]:
    async for token in _stream_openai_compatible(
        messages      = messages,
        api_key       = OPENROUTER_API_KEY,
        base_url      = "https://openrouter.ai/api/v1",
        model         = LLM_MODEL,
        provider_name = "OpenRouter",
    ):
        yield token


async def _stream_google(messages: List[dict]) -> AsyncGenerator[str, None]:
    if not GOOGLE_API_KEY:
        yield "Error: GOOGLE_API_KEY not configured."
        return

    from google import genai
    from google.genai import types

    client      = genai.Client(api_key=GOOGLE_API_KEY)
    system_text = _extract_system(messages)
    history     = _to_gemini_history(messages[:-1])
    user_query  = messages[-1]["content"]
    contents    = history + [{"role": "user", "parts": [{"text": user_query}]}]

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
            yield "Rate limit reached on Google Gemini. Please try again in a minute."
        else:
            logger.error(f"Google generation failed: {e}", exc_info=True)
            yield f"Error: {e}"


### PUBLIC API ###

_PROVIDERS = {
    "groq":       _stream_groq,
    "openrouter": _stream_openrouter,
    "google":     _stream_google,
}


async def stream(messages: List[dict]) -> AsyncGenerator[str, None]:
    provider_fn = _PROVIDERS.get(LLM_PROVIDER)
    if provider_fn is None:
        yield f"Error: Unknown LLM_PROVIDER '{LLM_PROVIDER}'. Choose from: {', '.join(_PROVIDERS)}."
        return

    async for token in provider_fn(messages):
        yield token
