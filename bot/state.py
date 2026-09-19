"""
Per-chat UI state (language, last response, pending question).
Profile data lives on the server.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import config


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


_states: dict[int, ChatState] = {}


def get(chat_id: int) -> ChatState:
    if chat_id not in _states:
        _states[chat_id] = ChatState()
    return _states[chat_id]


def reset(chat_id: int) -> ChatState:
    old = _states.get(chat_id)
    new = ChatState()
    if old:
        new.lang, new.lang_chosen, new.voice_on = old.lang, old.lang_chosen, old.voice_on
    _states[chat_id] = new
    return new


def session_id(chat_id: int) -> str:
    return f"tg:{chat_id}"
