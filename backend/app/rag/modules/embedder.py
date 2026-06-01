import logging
import time
from typing import List

import requests

from app.rag.config import (
    EMBEDDING_PROVIDER,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    EMBEDDING_BATCH_SIZE,
    OLLAMA_URL,
    HUGGINGFACE_API_KEY,
    HUGGINGFACE_MODEL,
    GOOGLE_API_KEY,
    GOOGLE_EMBEDDING_MODEL,
    CIRCUIT_BREAKER_ENABLED,
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(self, threshold: int, reset_timeout: int):
        self.threshold     = threshold
        self.reset_timeout = reset_timeout
        self.failures      = 0
        self.opened_at     = None

    @property
    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.time() - self.opened_at >= self.reset_timeout:
            self.failures  = 0
            self.opened_at = None
            return False
        return True

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.time()
            logger.error(
                f"Circuit breaker opened after {self.failures} failures. "
                f"Pausing for {self.reset_timeout}s."
            )

    def record_success(self):
        self.failures  = 0
        self.opened_at = None


_breaker = CircuitBreaker(
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS,
)


def _embed_ollama(texts: List[str]) -> List[List[float]]:
    url  = f"{OLLAMA_URL}/api/embed"
    resp = requests.post(
        url,
        json={"model": EMBEDDING_MODEL, "input": texts},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json().get("embeddings", [])


def _embed_google(texts: List[str]) -> List[List[float]]:
    import time
    from google import genai
    client  = genai.Client(api_key=GOOGLE_API_KEY)
    results = []
    for i, text in enumerate(texts):
        response = client.models.embed_content(
            model=GOOGLE_EMBEDDING_MODEL,
            contents=text,
        )
        results.append(response.embeddings[0].values)
        if i < len(texts) - 1:
            time.sleep(0.5)
    return results


def _embed_huggingface(texts: List[str]) -> List[List[float]]:
    url     = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{HUGGINGFACE_MODEL}"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    resp    = requests.post(url, headers=headers, json={"inputs": texts}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _call_provider(texts: List[str]) -> List[List[float]]:
    if EMBEDDING_PROVIDER == "ollama":
        return _embed_ollama(texts)
    elif EMBEDDING_PROVIDER == "google":
        return _embed_google(texts)
    elif EMBEDDING_PROVIDER == "huggingface":
        return _embed_huggingface(texts)
    else:
        raise ValueError(f"Unknown embedding provider: {EMBEDDING_PROVIDER}")


def _embed_with_retry(texts: List[str], retries: int = 3) -> List[List[float]]:
    if CIRCUIT_BREAKER_ENABLED and _breaker.is_open:
        raise RuntimeError(
            "Embedding service unavailable (circuit breaker open). Try again shortly."
        )

    delay      = 1.0
    last_error = None

    for attempt in range(retries):
        try:
            result = _call_provider(texts)
            _breaker.record_success()
            return result
        except Exception as e:
            last_error = e
            _breaker.record_failure()
            logger.warning(f"Embedding attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2

    raise RuntimeError(f"Embedding failed after {retries} attempts: {last_error}")


def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []

    all_embeddings: List[List[float]] = []

    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i: i + EMBEDDING_BATCH_SIZE]
        logger.info(
            f"Embedding batch {i // EMBEDDING_BATCH_SIZE + 1} "
            f"({len(batch)} texts) via {EMBEDDING_PROVIDER}"
        )
        batch_embeddings = _embed_with_retry(batch)
        all_embeddings.extend(batch_embeddings)

    return all_embeddings


def embed_single(text: str) -> List[float]:
    results = embed_texts([text])
    if not results:
        raise RuntimeError("Embedding returned empty result")
    return results[0]