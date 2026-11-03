"""
In-process, privacy-safe usage counters: aggregate numbers only -- never a session id, user id or
profile value. Reset on process restart; periodically snapshotted into MongoDB (the `metrics`
collection) when MONGODB_URI is set, so numbers survive restarts and can be charted over time.
Readable live at any time via GET /api/metrics, which returns {"uptime_s": <seconds>, **counters} --
a sparse dict, so a counter only appears once something has actually incremented it.

Counters, grouped by where they're incremented:
  llm.py            llm_requests_total     every complete_json / complete_text call into _chat
                     llm_fallback_used      succeeded on a model other than the primary
                     llm_rate_limit_waits   waited out a short 429 on the same model
                     llm_failures_401       auth failure (aborted immediately, no fallback)
                     llm_requests_failed    every model in the fallback chain failed
  nlp/normalise.py   extraction_rejected_low_confidence
                                            an LLM-extracted field update was below MIN_CONFIDENCE
  retrieval/service.py retrieval_hits       a scheme Q&A search returned at least one hit
                     retrieval_empty        search ran but returned nothing
                     retrieval_failures     search errored or timed out
  services/orchestrator.py
                     sessions_started       once per session, on its first turn
                     turns_total            once per chat()/answer() call
                     lang_en / lang_ta / lang_hi
                                            one per turn, by the request's language
                     off_topic_replies      the user's message didn't answer the pending question
                     sessions_completed     once per session, the first time it runs out of questions
                     questions_asked_total  added once per session at completion (len(s.asked)) --
                                            questions_asked_total / sessions_completed is the
                                            average interview length
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from datetime import UTC, datetime

from app.core import config

log = logging.getLogger("urimai.metrics")

_started_at = time.time()
_counters: Counter[str] = Counter()


def inc(name: str, by: int = 1) -> None:
    _counters[name] += by


def snapshot() -> dict:
    """Every counter plus process uptime -- what /api/metrics returns and what gets stored in MongoDB."""
    return {"uptime_s": round(time.time() - _started_at), **dict(_counters)}


def reset() -> None:
    """Tests only."""
    _counters.clear()


def _flush_once() -> None:
    if not config.MONGODB_URI:
        return
    from pymongo.errors import PyMongoError

    from app.core import db

    try:
        doc = {"ts": datetime.now(UTC), **snapshot()}
        db.shared()[config.MONGODB_DB][config.MONGODB_METRICS_COLLECTION].insert_one(doc)
    except PyMongoError as e:
        log.warning("metrics flush failed (%s)", db.explain(e))


async def flush_loop() -> None:
    """
    Writes one snapshot doc to MongoDB every config.METRICS_FLUSH_INTERVAL_S, forever.
    A no-op without MONGODB_URI -- counters stay readable live via GET /api/metrics regardless.
    """
    while True:
        await asyncio.sleep(config.METRICS_FLUSH_INTERVAL_S)
        _flush_once()
