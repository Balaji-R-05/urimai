"""All server settings, read from urimai/.env (shared with the Telegram bot) and the environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

SERVER_ROOT = Path(__file__).resolve().parents[2]  # urimai/server
load_dotenv(SERVER_ROOT.parent / ".env", override=True)

# LLM (Groq)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
# comma-separated; each Groq model has its own rate limit, so fallbacks add capacity
LLM_FALLBACK_MODELS = [m.strip() for m in os.getenv(
    "LLM_FALLBACK_MODELS", "openai/gpt-oss-20b,qwen/qwen3.8-27b").split(",") if m.strip()]
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low")
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "8"))
STT_MODEL = os.getenv("STT_MODEL", "whisper-large-v3")
SESSION_TTL_S = int(os.getenv("SESSION_TTL_S", "1800"))

# Scheme catalogue: MongoDB when MONGODB_URI is set, else the JSON seed in server/data/schemes.json
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGODB_DB = os.getenv("MONGODB_DB", "urimai")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "schemes")
SEED_PATH = SERVER_ROOT / "data" / "schemes.json"
LOG_DB_CALLS = os.getenv("LOG_DB_CALLS", "1").lower() not in ("0", "false", "no", "")  # see app/core/db.py

# Scheme retrieval for Q&A (app/retrieval: recursive chunks, dense + BM25 + RRF, cross-encoder rerank).
# In-memory search over the loaded catalogue. Off -> the extractor's scheme pick is used as before.
RETRIEVAL_ENABLED = os.getenv("RETRIEVAL_ENABLED", "1").lower() not in ("0", "false", "no", "")
RETRIEVAL_TIMEOUT_S = float(os.getenv("RETRIEVAL_TIMEOUT_S", "4"))
RETRIEVAL_MIN_SCORE = float(os.getenv("RETRIEVAL_MIN_SCORE", "0.3"))  # reranker relevance to add a scheme
# Where scheme search runs: "atlas" = MongoDB Atlas Vector Search + Atlas Search over the scheme_chunks collection
# (filled by the seed command); "memory" = in-process index over the loaded catalogue (tests, no MongoDB).
RETRIEVAL_BACKEND = os.getenv("RETRIEVAL_BACKEND", "atlas" if MONGODB_URI else "memory")
MONGODB_CHUNKS_COLLECTION = os.getenv("MONGODB_CHUNKS_COLLECTION", "scheme_chunks")
# Chunking (characters). Section text is split recursively; every chunk gets a "scheme | section" header.
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "300"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "60"))
# Models (fastembed / ONNX, downloaded once into MODEL_CACHE). "hash" / "none" = no model.
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
RERANK_MODEL = os.getenv("RERANK_MODEL", "jinaai/jina-reranker-v2-base-multilingual")
MODEL_CACHE = os.getenv("MODEL_CACHE", str(SERVER_ROOT / ".models"))
HASH_DIM = int(os.getenv("HASH_DIM", "512"))
CANDIDATES = int(os.getenv("RETRIEVE_CANDIDATES", "30"))  # results taken from each of dense and keyword search
RERANK_POOL = int(os.getenv("RERANK_POOL", "20"))  # fused results the reranker scores (its cost grows with this)
RRF_K = int(os.getenv("RRF_K", "60"))
