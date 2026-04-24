"""
Nexus RAG Pipeline
==================
A custom RAG pipeline (no LangChain) inspired by the reference implementation.
Handles PDF ingestion, chunking, embedding, vector storage, and retrieval.

Architecture:
  PDF Upload → Text Extraction → Chunking → Embedding → ChromaDB
  Query → Embed Query → Semantic Search → Ranked Chunks → Ollama LLM → Streamed Answer

Requirements:
  - Ollama must be running locally: https://ollama.com
  - Pull the models before starting:
      ollama pull llama3.2
      ollama pull nomic-embed-text
"""

from __future__ import annotations

import json
import re
import hashlib
from pathlib import Path
from typing import Iterator, Optional

import chromadb
import PyPDF2
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


# ============================================================
# CONFIGURATION
# ============================================================

CHUNK_SIZE = 600
CHUNK_OVERLAP = 80
TOP_K_RESULTS = 6

OLLAMA_LLM_MODEL = "llama3.2"
OLLAMA_EMBED_MODEL = "nomic-embed-text"

# Absolute path so ChromaDB works regardless of working directory
CHROMA_PATH = str(Path(__file__).resolve().parent.parent.parent / "chroma_db")
COLLECTION_NAME = "nexus_documents"

# ============================================================
# SINGLETONS — initialised once at module load
# ============================================================

_chroma_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None
_embeddings: Optional[OllamaEmbeddings] = None
_llm: Optional[ChatOllama] = None


def get_chroma_collection() -> chromadb.Collection:
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Nexus per-course document store"},
        )
        print(f"[RAG] ChromaDB collection '{COLLECTION_NAME}' ready")
    return _collection


def get_embeddings() -> OllamaEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OllamaEmbeddings(model=OLLAMA_EMBED_MODEL)
        print(f"[RAG] Embeddings model ready: {OLLAMA_EMBED_MODEL}")
    return _embeddings


def get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        _llm = ChatOllama(model=OLLAMA_LLM_MODEL)
        print(f"[RAG] LLM ready: {OLLAMA_LLM_MODEL}")
    return _llm


def check_ollama_running() -> bool:
    """Ping Ollama to verify it's reachable before handling requests."""
    import httpx
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


# ============================================================
# DOCUMENT PROCESSING
# ============================================================

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF given its raw bytes."""
    import io
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks, preferring sentence boundaries.

    Why overlap?
    A relevant passage might straddle a chunk boundary — overlap ensures
    neither half loses the surrounding context needed to be useful.
    """
    # Normalise whitespace
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end < len(text):
            # Try to break at the last sentence boundary before `end`
            window = text[start:end]
            last_break = max(
                window.rfind(". "),
                window.rfind("? "),
                window.rfind("! "),
                window.rfind("\n\n"),
            )
            if last_break > chunk_size // 2:
                end = start + last_break + 1

        chunk = text[start:end].strip()
        if len(chunk) > 40:          # skip tiny remnants
            chunks.append(chunk)

        start = end - overlap

    return chunks


def stable_doc_id(filename: str, chunk_index: int) -> str:
    """
    Produce a deterministic chunk ID so re-uploading the same file
    overwrites rather than duplicates.
    """
    stem = hashlib.md5(filename.encode()).hexdigest()[:8]
    return f"{stem}_{chunk_index}"


# ============================================================
# INDEXING
# ============================================================

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using LangChain's OllamaEmbeddings."""
    return get_embeddings().embed_documents(texts)


def embed_query(query: str) -> list[float]:
    """Embed a single query string using LangChain's OllamaEmbeddings."""
    return get_embeddings().embed_query(query)


def index_pdf(file_bytes: bytes, filename: str) -> dict:
    """
    Full ingestion pipeline for a single PDF:
      bytes → text → chunks → embeddings (Ollama) → ChromaDB
    Returns a summary dict.
    """
    collection = get_chroma_collection()

    print(f"[RAG] Extracting text from: {filename}")
    text = extract_text_from_pdf(file_bytes)

    if not text.strip():
        raise ValueError(f"Could not extract text from {filename}. Is it a scanned image PDF?")

    chunks = chunk_text(text)
    print(f"[RAG] {filename} → {len(chunks)} chunks")

    # Embed all chunks via Ollama in one batch request
    print(f"[RAG] Embedding {len(chunks)} chunks with {OLLAMA_EMBED_MODEL}…")
    embeddings = embed_texts(chunks)

    ids = [stable_doc_id(filename, i) for i in range(len(chunks))]
    metadatas = [{"source": filename, "chunk_index": i} for i in range(len(chunks))]

    # Upsert so re-uploads are idempotent
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )

    return {"filename": filename, "chunks_indexed": len(chunks)}


# ============================================================
# RETRIEVAL
# ============================================================

def retrieve(query: str, n_results: int = TOP_K_RESULTS) -> list[dict]:
    """
    Embed the query and return the top-k most semantically similar chunks.
    Each result: { content, source, relevance_score }
    """
    collection = get_chroma_collection()

    query_embedding = embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    formatted: list[dict] = []
    for i in range(len(results["documents"][0])):
        # ChromaDB returns L2 distance; convert to a [0,1] similarity score
        distance = results["distances"][0][i]
        relevance = round(1 / (1 + distance), 3)
        formatted.append(
            {
                "content": results["documents"][0][i],
                "source": results["metadatas"][0][i]["source"],
                "chunk_index": results["metadatas"][0][i]["chunk_index"],
                "relevance_score": relevance,
            }
        )

    return formatted


def list_indexed_files() -> list[str]:
    """Return a deduplicated list of all indexed filenames."""
    collection = get_chroma_collection()
    all_data = collection.get(include=["metadatas"])

    sources = set()

    for m in all_data["metadatas"]:
        source = m.get("source")
        if isinstance(source, str):
            sources.add(source)

    return sorted(sources)


def delete_file_from_index(filename: str) -> int:
    """Remove all chunks belonging to `filename`. Returns count deleted."""
    collection = get_chroma_collection()
    all_data = collection.get(include=["metadatas"])

    ids_to_delete = [
        all_data["ids"][i]
        for i, m in enumerate(all_data["metadatas"])
        if m["source"] == filename
    ]

    if ids_to_delete:
        collection.delete(ids=ids_to_delete)

    return len(ids_to_delete)


# ============================================================
# ANSWER GENERATION (streaming)
# ============================================================

SYSTEM_PROMPT = """You are SARS AI, an academic assistant embedded inside a course hub.
You answer questions STRICTLY using the provided course materials — never create your own facts.

Rules:
1. Ground every claim in the retrieved context below.
2. If the answer isn't in the context, say: "I couldn't find that in the uploaded materials."
3. Cite sources inline using the format [source: filename, chunk N].
4. Be concise but complete. Use markdown (bold, bullet lists) where it aids clarity.
5. Do not refer to the retrieval mechanics — just answer naturally."""


def build_context_block(chunks: list[dict]) -> str:
    """Format retrieved chunks into a context string for the prompt."""
    lines = ["## Retrieved Course Material\n"]
    for i, chunk in enumerate(chunks, 1):
        lines.append(
            f"[Chunk {i} | source: {chunk['source']}, chunk {chunk['chunk_index']} | "
            f"relevance: {chunk['relevance_score']}]\n{chunk['content']}\n"
        )
    return "\n".join(lines)


def stream_answer(query: str, conversation_history: list[dict]) -> Iterator[str]:
    """
    Streaming RAG answer generation via LangChain's ChatOllama.

    Flow:
      1. Retrieve relevant chunks for the query
      2. Emit citation metadata (before any tokens)
      3. Build a LangChain message list from conversation history + context
      4. Stream tokens from ChatOllama and forward as SSE events
    """
    llm = get_llm()

    # Step 1 — Retrieve
    chunks = retrieve(query)

    if not chunks:
        yield "data: " + json.dumps({"type": "error", "text": "No documents indexed yet. Please upload a PDF first."}) + "\n\n"
        return

    # Step 2 — Emit citations before any tokens
    citations = [
        {"source": c["source"], "chunk": c["chunk_index"], "relevance": c["relevance_score"]}
        for c in chunks
    ]
    yield "data: " + json.dumps({"type": "citations", "citations": citations}) + "\n\n"

    # Step 3 — Build LangChain message list
    context_block = build_context_block(chunks)
    augmented_user_message = f"{context_block}\n\n---\n\n**Question:** {query}"

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    # Map conversation history dicts → LangChain message objects
    for turn in conversation_history[-6:]:
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "assistant":
            messages.append(AIMessage(content=turn["content"]))

    messages.append(HumanMessage(content=augmented_user_message))

    # Step 4 — Stream tokens from ChatOllama
    for chunk in llm.stream(messages):
        token = chunk.content
        if token:
            yield "data: " + json.dumps({"type": "token", "text": token}) + "\n\n"

    yield "data: " + json.dumps({"type": "done"}) + "\n\n"


def answer_question(query: str, conversation_history: Optional[list] = None) -> dict:
    if conversation_history is None:
        conversation_history = []

    llm = get_llm()
    chunks = retrieve(query)

    if not chunks:
        return {
            "answer": "I couldn't find that in the uploaded materials.",
            "chunks": []
        }

    context_block = build_context_block(chunks)
    augmented_user_message = f"{context_block}\n\n---\n\n**Question:** {query}"

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    for turn in conversation_history[-6:]:
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "assistant":
            messages.append(AIMessage(content=turn["content"]))

    messages.append(HumanMessage(content=augmented_user_message))

    response = llm.invoke(messages)

    return {
        "answer": response.content,
        "chunks": chunks,
    }