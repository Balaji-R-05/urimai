"""
In-process, privacy-safe usage counters: aggregate numbers only -- never a session id, user id or
profile value. Reset on process restart; periodically snapshotted into MongoDB (the `metrics`
collection) when MONGODB_URI is set, so numbers survive restarts and can be charted over time.
Readable live at any time via GET /api/metrics.
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
    """Writes one snapshot doc to MongoDB every config.METRICS_FLUSH_INTERVAL_S, forever.
    A no-op without MONGODB_URI -- counters stay readable live via GET /api/metrics regardless."""
    while True:
        await asyncio.sleep(config.METRICS_FLUSH_INTERVAL_S)
        _flush_once()
