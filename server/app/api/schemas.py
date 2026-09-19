"""Request bodies for the API. Unknown fields (e.g. the bot's "channel") are ignored."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Lang = Literal["en", "ta", "hi"]


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2000)
    lang: Lang = "en"


class AnswerRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    field: str
    value: Any = None
    skip: bool = False
    lang: Lang = "en"


class SessionRequest(BaseModel):
    session_id: str


class EvaluateRequest(BaseModel):
    profile: dict
    lang: Lang = "en"
