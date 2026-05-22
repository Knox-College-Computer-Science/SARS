from pathlib import Path

# Base paths

RAG_DIR     = Path(__file__).resolve().parent          # app/rag/
APP_DIR     = RAG_DIR.parent                           # app/
BACKEND_DIR = APP_DIR.parent                           # backend/

STORAGE_DIR     = BACKEND_DIR / "rag_storage"
UPLOAD_DIR      = BACKEND_DIR / "RAG_Uploads"
CHROMA_DIR      = STORAGE_DIR / "chroma_db"
CHUNK_STORE_DIR = STORAGE_DIR / "chunk_store"
EVAL_LOG_DIR    = STORAGE_DIR / "eval_logs"


# Models
EMBED_MODEL  = "nomic-embed-text"
LLM_MODEL    = "llama3.2"
VISION_MODEL = "llava"

#  Extraction

EXTRACTION_STRATEGY = "fast"
EXTRACT_IMAGES      = True   # Images enabled

#  Chunking
CHUNK_MIN_CHARS            = 200   # Merge fragments smaller than this
CHUNK_MAX_CHARS            = 600   # Hard cap per retrieval chunk
CHUNK_SEMANTIC_TRIGGER     = 600   # Use semantic split above this size
SEMANTIC_BREAKPOINT_PCTILE = 85    # Cosine distance percentile for splitting
IMAGE_MIN_CAPTION_CHARS    = 20    # Skip captions shorter than this

#Hybrid search weights
VECTOR_WEIGHT = 0.6
BM25_WEIGHT   = 0.4

#  Retrieval
TOP_K_VECTOR = 20   # Candidates from vector search
TOP_K_BM25   = 20   # Candidates from BM25 keyword search
TOP_K_FINAL  = 5    # Final top-K sent to LLM after RRF fusion

#  Multi-query
MULTIQUERY_VARIANTS = 2

# Conversation memory
MEMORY_WINDOW = 6

MULTIQUERY_PROMPT_TEMPLATE = """\
Generate {n} alternative search queries for the question below.
Each alternative should use different wording but ask the same thing.
Return ONLY the alternatives, one per line, no numbering, no extra text.

Question: {query}

Alternatives:"""

MULTIQUERY_ENABLED = True

# ChromaDB
COLLECTION_PREFIX = "sars_"   # sars_course_1, sars_course_2, etc.

# Ollama retry
OLLAMA_MAX_RETRIES = 3    # Attempts before giving up
OLLAMA_RETRY_DELAY = 1.0  # Base delay in seconds

#  Evaluation logging
EVAL_LOGGING_ENABLED = True
EVAL_LOG_FILE        = EVAL_LOG_DIR / "retrieval_log.jsonl"

#  Auto-create storage directories on import
for _dir in [STORAGE_DIR, UPLOAD_DIR, CHROMA_DIR, CHUNK_STORE_DIR, EVAL_LOG_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)