import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

### PATHS ###

RAG_UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "RAG_Uploads"
RAG_UPLOADS_DIR.mkdir(exist_ok=True)

PARSE_CACHE_DIR = Path(__file__).resolve().parent / "storage" / "parse_cache"
PARSE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

### EMBEDDING ###

EMBEDDING_PROVIDER  = os.getenv("EMBEDDING_PROVIDER", "google")
EMBEDDING_MODEL     = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSION = 768
EMBEDDING_BATCH_SIZE = 100

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434") # Not used in the current iteration

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "") # Fallback Option
HUGGINGFACE_MODEL   = os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-4B") # Fallback Option

GOOGLE_API_KEY          = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_EMBEDDING_MODEL  = "gemini-embedding-001"

### GROQ ###

LLM_PROVIDER    = os.getenv("LLM_PROVIDER", "groq")
_default_models = {
    "groq":       "llama-3.3-70b-versatile",
    "google":     "gemini-2.0-flash",
}
LLM_MODEL       = os.getenv("LLM_MODEL", _default_models.get(LLM_PROVIDER, "llama-3.3-70b-versatile"))
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS  = 1024

GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")

### CHUNKING ###

CHUNK_MIN_CHARS    = 300
CHUNK_MAX_CHARS    = 1200
CHUNK_OVERLAP_CHARS = 100
SLIDE_MERGE_THRESHOLD = 400


### RETRIEVAL ###

VECTOR_SEARCH_TOP_K = 20
BM25_SEARCH_TOP_K   = 20

RERANK_TOP_K     = 8
RERANK_THRESHOLD = 0.3
RERANKING_BATCH_SIZE = 32

QUERY_VARIANTS_COUNT        = 3
HYBRID_SEARCH_WEIGHT_VECTOR = 0.6
HYBRID_SEARCH_WEIGHT_BM25   = 0.4


### CONTEXT WINDOW ###

TOTAL_CONTEXT_BUDGET  = 6000
HISTORY_MAX_TOKENS    = 2000
RETRIEVAL_MAX_TOKENS  = 4000
RETRIEVAL_MEMORY_WINDOW = 10


### QUALITY GATES ###

QUALITY_TIER_HIGH_MIN_CHARS      = 150
QUALITY_TIER_HIGH_MIN_DIVERSITY  = 0.5
QUALITY_TIER_MEDIUM_MIN_CHARS    = 80
QUALITY_TIER_MEDIUM_MIN_DIVERSITY = 0.35
QUALITY_TIER_LOW_MIN_CHARS       = 20


### CIRCUIT BREAKER ###

CIRCUIT_BREAKER_ENABLED           = True
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS = 30


### INDEXING ###

DUPLICATE_DETECTION_ENABLED = True
PARSE_RESULT_CACHE_ENABLED  = True

IMAGE_EXTRACTION_ENABLED = False
IMAGE_CAPTION_ENABLED    = True
IMAGE_CAPTION_MODEL      = LLM_MODEL


### LOGGING ###

EVAL_LOG_ENABLED = True


### FEATURE FLAGS ###

MULTIQUERY_ENABLED      = False # False due to rate limits. If running local, can enable.
CONTEXT_PACKING_ENABLED = True
SIBLING_CONTEXT_ENABLED = True
RERANKING_ENABLED       = True
BM25_CACHE_ENABLED      = True

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"