"""
Per-chat UI state (language, last response, pending question).
Profile data lives on the server.
"""

from __future__ import annotations
import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
import config

MAX_CHATS = 20_000  # bound long-running memory use; evicts the least-recently-touched chat


@dataclass
class ChatState:
    lang: str = config.DEFAULT_LANG
    lang_chosen: bool = False
    voice_on: bool = config.VOICE_REPLIES_DEFAULT
    last: dict | None = None            # last server response
    card_msg_id: int | None = None
    card_sig: tuple | None = None
    q_id: int = 0                       # increments with every question, so stale button taps are ignored
    question: dict | None = None
    last_user_text: str | None = None
    hints_shown: set = field(default_factory=set)
    feedback_for: str | None = None     # scheme_id awaiting a "what's wrong" reply, or None


_states: "OrderedDict[int, ChatState]" = OrderedDict()
_locks: dict[int, asyncio.Lock] = {}


# Drops the least-recently-touched chats once we're over MAX_CHATS. A chat's lock is
# only dropped alongside it when that lock is free, so an in-flight handler never
# loses the lock object it's holding.
def _evict_lru() -> None:
    while len(_states) > MAX_CHATS:
        oldest_id, _ = _states.popitem(last=False)
        lk = _locks.get(oldest_id)
        if lk is None or not lk.locked():
            _locks.pop(oldest_id, None)


# Returns the per-chat lock, creating it if necessary. Handlers hold this for their
# whole run so concurrent updates for the same chat (e.g. a double-tapped button)
# can't interleave reads/writes of its ChatState.
def lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in _locks:
        _locks[chat_id] = asyncio.Lock()
    return _locks[chat_id]


# Returns the ChatState for a given chat_id, creating it if necessary.
def get(chat_id: int) -> ChatState:
    st = _states.get(chat_id)
    if st is None:
        st = _states[chat_id] = ChatState()
    else:
        _states.move_to_end(chat_id)
    _evict_lru()
    return st


# Resets the ChatState for a given chat_id, preserving language and voice settings.
def reset(chat_id: int) -> ChatState:
    old = _states.get(chat_id)
    new = ChatState()
    if old:
        new.lang, new.lang_chosen, new.voice_on = old.lang, old.lang_chosen, old.voice_on
    _states[chat_id] = new
    _states.move_to_end(chat_id)
    _evict_lru()
    return new


# Returns a session_id for the backend, given a chat_id.
def session_id(chat_id: int) -> str:
    return f"tg:{chat_id}"
