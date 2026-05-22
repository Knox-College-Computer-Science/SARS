from typing import List
import time
import logging

import ollama as _ollama

from app.rag.config import EMBED_MODEL, OLLAMA_MAX_RETRIES, OLLAMA_RETRY_DELAY

logger = logging.getLogger("sars.rag.embedder")


def embed_texts(texts: List[str]) -> List[List[float]]:

    if not texts:
        return []

    last_error = None
    for attempt in range(OLLAMA_MAX_RETRIES):
        try:
            response = _ollama.embed(model=EMBED_MODEL, input=texts)
            embeddings = response.get("embeddings", [])
            if not embeddings:
                raise ValueError("Ollama returned empty embeddings")
            logger.debug(f"Embedded {len(texts)} texts (attempt {attempt + 1})")
            return embeddings

        except Exception as e:
            last_error = e
            if attempt < OLLAMA_MAX_RETRIES - 1:
                wait = OLLAMA_RETRY_DELAY * (2 ** attempt)  # 1s, 2s, 4s
                logger.warning(f"Embedding attempt {attempt + 1} failed, retrying in {wait}s: {e}")
                time.sleep(wait)
            else:
                logger.error(f"Embedding failed after {OLLAMA_MAX_RETRIES} attempts: {e}")

    raise RuntimeError(
        f"Embedding failed after {OLLAMA_MAX_RETRIES} attempts. "
        f"Is Ollama running? Last error: {last_error}"
    )


def embed_single(text: str) -> List[float]:

    vectors = embed_texts([text])
    return vectors[0]