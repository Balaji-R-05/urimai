"""Scheme retrieval for Q&A: which schemes (and which section) is the user's question about?

Backend (config.RETRIEVAL_BACKEND): "atlas" = MongoDB Atlas Vector Search + Atlas Search (app/retrieval/atlas.py),
"memory" = in-process index over the loaded catalogue (app/retrieval/search.py). Both do:
  chunking  : scheme -> section (overview / eligibility / documents / how_to_apply) x language = parent;
              parent -> recursive split (paragraph > line > sentence > clause > word) = children with a
              "<scheme> | <section>" header
  retrieval : dense (multilingual MiniLM) + BM25 (words + char 4-grams), each top-30, fused with RRF,
              then a multilingual cross-encoder (jina-reranker-v2) reranks the pool
Retrieval only picks WHICH schemes to talk about. Eligibility still comes from app/engine/rules.py.
Every failure (models missing, timeout) returns None and the extractor's pick is used unchanged.
"""
from __future__ import annotations

import asyncio
import logging

from app.core import config

log = logging.getLogger("urimai.retrieval")

# retrieval section -> answerer topic
SECTION_TOPIC = {"overview": "general", "eligibility": "eligibility", "documents": "documents",
                 "how_to_apply": "how_to_apply"}
MAX_SCHEMES = 3


def _search(text: str, state: str | None = None) -> list[dict]:
    """state: the user's state code, if known; limits results to central schemes plus that state's."""
    if config.RETRIEVAL_BACKEND == "atlas":
        from app.retrieval import atlas
        return atlas.retrieve(text, k=6, state=state)
    from app.retrieval.search import retrieve
    return retrieve(text, k=6)


def warmup() -> None:
    """Load the models (and, in memory mode, the chunk vectors) once, so the first real question is fast."""
    if not config.RETRIEVAL_ENABLED:
        return
    try:
        if config.RETRIEVAL_BACKEND == "atlas":
            from app.retrieval import atlas
            atlas.warmup()
        else:
            _search("warmup")
        log.info("retrieval ready (%s)", config.RETRIEVAL_BACKEND)
    except Exception as e:
        log.warning("retrieval warmup failed (%s); Q&A uses the extractor's scheme pick", e)


async def search(text: str, state: str | None = None) -> list[dict] | None:
    """Ranked section hits, or None if retrieval is off, failed or timed out."""
    if not config.RETRIEVAL_ENABLED or not text.strip():
        return None
    try:
        return await asyncio.wait_for(asyncio.to_thread(_search, text, state), config.RETRIEVAL_TIMEOUT_S)
    except Exception as e:  # ImportError, model load, TimeoutError, ...
        log.warning("retrieval failed: %s: %s", type(e).__name__, e)
        return None


def confident(hits: list[dict], min_score: float = config.RETRIEVAL_MIN_SCORE) -> list[dict]:
    """Hits we trust enough to act on: reranker relevance >= min_score; without a reranker, only the top hit."""
    if not hits:
        return []
    if not hits[0].get("reranked"):
        return hits[:1]
    return [h for h in hits if h["score"] >= min_score]


def merge_question(question: dict, hits: list[dict] | None) -> dict | None:
    """Combine the extractor's {scheme_ids, topic} with retrieval.

    - The user named a scheme and asked something specific -> keep the extractor's ids (it saw the name).
    - Broad question ("any housing scheme?") or no ids -> retrieved schemes first, then the extractor's.
    - Topic "general" -> the best hit's section (documents / eligibility / how_to_apply) when it has one.
    """
    ext_ids, topic = list(question.get("scheme_ids") or []), question.get("topic") or "general"
    good = confident(hits or [])
    ret_ids = list(dict.fromkeys(h["scheme_id"] for h in good))
    if ext_ids and topic != "general":
        ids, source = ext_ids, "extractor"
    else:
        ids = list(dict.fromkeys(ret_ids + ext_ids))
        source = "retrieval" if ret_ids and not ext_ids else ("both" if ret_ids else "extractor")
    ids = ids[:MAX_SCHEMES]
    if not ids:
        return None
    if topic == "general" and good:
        topic = SECTION_TOPIC.get(good[0]["section"], "general")
    passages = [{"scheme_id": h["scheme_id"], "section": h["section"], "text": h["context"]}
                for h in good if h["scheme_id"] in ids][:4]
    return {"scheme_ids": ids, "topic": topic, "source": source, "passages": passages}


def trace_view(hits: list[dict] | None) -> list[dict]:
    """Compact per-hit view of every stage, for the turn trace."""
    return [{"scheme": h["scheme_id"], "section": h["section"], "dense_rank": h.get("dense_rank"),
             "bm25_rank": h.get("bm25_rank"), "rrf": round(h.get("rrf", 0), 4),
             "rerank": None if h.get("rerank_score") is None else round(h["rerank_score"], 3)}
            for h in (hits or [])]
