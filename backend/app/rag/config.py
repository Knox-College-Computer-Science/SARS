from pathlib import Path

RAG_BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR  = RAG_BASE_DIR.parent.parent
STORAGE_DIR  = BACKEND_DIR / "rag_storage"

CHROMA_DIR      = STORAGE_DIR / "chroma_db"      # ChromaDB persistent store
CHUNK_STORE_DIR = STORAGE_DIR / "chunk_store"    # JSON files for context/parents
EVAL_LOG_DIR    = STORAGE_DIR / "eval_logs"      # Retrieval evaluation logs
UPLOAD_DIR      = BACKEND_DIR / "RAG_Uploads"    # Raw uploaded PDFs

### Embedding ###

EMBED_MODEL      = "nomic-embed-text"
EMBED_DIMENSIONS = 768

### Generation ###

LLM_MODEL    = "llama3.2"
VISION_MODEL = "llava"        # For image captioning
MEMORY_WINDOW = 6             # Number of conversation turns sent to LLM

### Chunking Thresholds ###

CHUNK_MIN_CHARS               = 200
CHUNK_SEMANTIC_TRIGGER        = 600
SEMANTIC_BREAKPOINT_PERCENTILE = 80

IMAGE_MIN_CAPTION_CHARS = 20

### Retrieval ###

TOP_K_VECTOR   = 20
TOP_K_BM25     = 20
TOP_K_FINAL    =  5

### Hybrid Search Weights ###

VECTOR_WEIGHT  = 0.6
BM25_WEIGHT    = 0.4

DEDUP_JACCARD_THRESHOLD = 0.85

### Multi-query expansion ###
MULTIQUERY_ENABLED = True
MULTIQUERY_VARIANTS = 3

# Prompt used to generate query alternatives.

MULTIQUERY_PROMPT_TEMPLATE = """\
Generate {n} alternative search queries for the question below.
Each alternative should use different wording but ask the same thing.
Return ONLY the alternatives, one per line, no numbering, no extra text.

Question: {query}

Alternatives:"""

### ChromaDB ###

COLLECTION_PREFIX = "SARS_"

###  Evaluation logging ###

EVAL_LOGGING_ENABLED = True
EVAL_LOG_FILE = EVAL_LOG_DIR / "retrieval_log.jsonl"

# Ensure storage directories exist
for _dir in [STORAGE_DIR, CHROMA_DIR, CHUNK_STORE_DIR, EVAL_LOG_DIR, UPLOAD_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)