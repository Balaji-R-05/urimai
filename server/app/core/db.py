"""MongoDB client that logs every database call, e.g.

    urimai.db: find urimai.schemes -> 10 docs in 38 ms

Connection housekeeping (hello, ping, auth) is not logged. Set LOG_DB_CALLS=0 to turn the log off.
"""
from __future__ import annotations

import logging

from pymongo import MongoClient, monitoring

from app.core import config

log = logging.getLogger("urimai.db")

LOGGED = {"find", "getMore", "aggregate", "count", "distinct", "insert", "update", "delete", "findAndModify",
          "createIndexes"}


class CommandLog(monitoring.CommandListener):
    def __init__(self):
        self._pending: dict[int, str] = {}

    def started(self, event):
        if event.command_name in LOGGED:
            target = event.command.get(event.command_name)
            coll = target if isinstance(target, str) else event.command.get("collection", "")
            self._pending[event.request_id] = f"{event.command_name} {event.database_name}.{coll}"

    def succeeded(self, event):
        what = self._pending.pop(event.request_id, None)
        if what is None:
            return
        reply = event.reply
        cursor = reply.get("cursor", {})
        if "firstBatch" in cursor or "nextBatch" in cursor:
            result = f"{len(cursor.get('firstBatch', cursor.get('nextBatch', [])))} docs"
        elif "n" in reply:
            result = f"{reply['n']} docs" + (f", {reply['nModified']} modified" if "nModified" in reply else "")
        else:
            result = "ok"
        log.info("%s -> %s in %d ms", what, result, event.duration_micros // 1000)

    def failed(self, event):
        what = self._pending.pop(event.request_id, None)
        if what is not None:
            log.warning("%s failed after %d ms: %s", what, event.duration_micros // 1000, event.failure)


def client(timeout_ms: int = 5000) -> MongoClient:
    """A new client; close it when done (startup load, seed command)."""
    listeners = [CommandLog()] if config.LOG_DB_CALLS else []
    return MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=timeout_ms, event_listeners=listeners)


def explain(e: Exception) -> str:
    """One-line reason for a failed database call, with the usual fix."""
    from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError
    if isinstance(e, ServerSelectionTimeoutError):
        return ("can't reach MongoDB (network down, or this IP isn't in the Atlas Network Access list); "
                "try again in a moment")
    if isinstance(e, OperationFailure) and e.code in (8000, 18):
        return "MongoDB rejected the login: check the user and password in MONGODB_URI"
    if isinstance(e, ConfigurationError):
        return f"MONGODB_URI looks wrong: {e}"
    return f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"


_shared: MongoClient | None = None


def shared() -> MongoClient:
    """One long-lived client (connection pool) for per-request queries such as scheme search."""
    global _shared
    if _shared is None:
        _shared = client()
    return _shared
