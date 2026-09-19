"""Cross-encoder reranker (fastembed ONNX). Scores (query, chunk) pairs jointly, so it catches meaning
the bi-encoder / BM25 stage misses, including Tamil or Hindi queries against English chunks.
Returns None when no model is available; the caller then keeps the fused order."""
from __future__ import annotations

import logging
import math
from functools import lru_cache

from app.core import config

log = logging.getLogger("urimai.retrieval")


@lru_cache(maxsize=1)
def _model():
    if config.RERANK_MODEL.lower() in ("none", ""):
        return None
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        return TextCrossEncoder(config.RERANK_MODEL, cache_dir=config.MODEL_CACHE)
    except Exception as e:
        log.warning("reranker %s unavailable (%s); using fused order", config.RERANK_MODEL, e)
        return None


def rerank(query: str, texts: list[str]) -> list[float] | None:
    """Relevance in [0, 1] per text, or None if reranking is off / failed."""
    model = _model()
    if model is None or not texts:
        return None
    try:
        return [1 / (1 + math.exp(-s)) for s in model.rerank(query, texts, batch_size=16)]
    except Exception as e:
        log.warning("rerank failed (%s); using fused order", e)
        return None
