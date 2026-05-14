"""
Text Embedding

"""

import logging
from typing import Optional

import ollama as _ollama

from app.rag.config import EMBED_MODEL

logger = logging.getLogger("nexus.rag.embedder")


def check_ollama_running() -> bool:
    """Return True if Ollama is reachable, False otherwise."""
    try:
        _ollama.list()
        return True
    except Exception:
        return False


def check_model_available(model_name: str) -> bool:
    """Return True if a specific model is pulled in Ollama."""
    try:
        models = _ollama.list()
        # models is {"models": [{"name": "llama3.2:latest", ...}, ...]}
        available = [
            m.get("name", "").split(":")[0]
            for m in models.get("models", [])
        ]
        return model_name in available
    except Exception:
        return False


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of texts using nomic-embed-text.

    """
    if not texts:
        return []

    # Filter out empty strings — Ollama returns errors for empty inputs
    clean = [t if t.strip() else " " for t in texts]

    try:
        response = _ollama.embed(model=EMBED_MODEL, input=clean)
        embeddings = response.get("embeddings") or response.get("embedding")
        if embeddings is None:
            raise ValueError(f"Unexpected Ollama embed response shape: {list(response.keys())}")
        return embeddings
    except Exception as e:
        logger.error(f"Embedding failed ({EMBED_MODEL}): {e}")
        raise RuntimeError(
            f"Embedding failed. Is Ollama running with {EMBED_MODEL} pulled? "
            f"Run: ollama pull {EMBED_MODEL}\n"
            f"Original error: {e}"
        )


def embed_single(text: str) -> list[float]:
    """
    Embed one text. Used for query embedding at retrieval time.
    Wraps embed_texts for a consistent interface.
    """
    return embed_texts([text])[0]