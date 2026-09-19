"""In-memory session store. No database; nothing persists after expiry (privacy by design)."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from app.core import config


@dataclass
class Session:
    id: str
    profile: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    asked: dict = field(default_factory=dict)      # field -> times asked
    skipped: set = field(default_factory=set)
    history: list = field(default_factory=list)    # [{"role": "user"|"assistant", "text": str}]
    last_field: str | None = None
    turn: int = 0
    last_response: dict | None = None
    updated_at: float = field(default_factory=time.time)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_sessions: dict[str, Session] = {}


def get(session_id: str) -> Session:
    now = time.time()
    for sid in [s for s, v in _sessions.items() if now - v.updated_at > config.SESSION_TTL_S]:
        _sessions.pop(sid, None)
    s = _sessions.get(session_id)
    if s is None:
        s = _sessions[session_id] = Session(id=session_id)
    s.updated_at = now
    return s


def peek(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def reset(session_id: str) -> None:
    _sessions.pop(session_id, None)
