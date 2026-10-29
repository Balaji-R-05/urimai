"""
Text-to-speech for voice replies (gTTS -> MP3).
Telegram plays MP3 sent via sendVoice as a voice bubble.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
from collections import OrderedDict

from gtts import gTTS

log = logging.getLogger("urimai.tts")
MAX_CACHE = 200
_cache: OrderedDict[str, bytes] = OrderedDict()


def _synth(text: str, lang: str) -> bytes:
    lang = lang if lang in ("ta", "hi", "en") else "en"
    tld = "co.in" if lang == "en" else "com"  # Indian English accent
    buf = io.BytesIO()
    gTTS(text=text, lang=lang, tld=tld).write_to_fp(buf)
    return buf.getvalue()


async def speak(text: str, lang: str) -> bytes | None:
    key = hashlib.sha1(f"{lang}:{text}".encode()).hexdigest()
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    try:
        audio = await asyncio.wait_for(asyncio.to_thread(_synth, text[:600], lang), timeout=15)
    except Exception as e:
        # Network / gTTS failures must never block the text reply
        log.warning("TTS failed: %s", e)
        return None
    _cache[key] = audio
    if len(_cache) > MAX_CACHE:
        _cache.popitem(last=False)  # evict least-recently-used entry
    return audio
