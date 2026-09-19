"""Groq wrapper: JSON completions, text completions and speech-to-text, all with timeouts."""
from __future__ import annotations

import asyncio
import json
import logging
import re

from groq import AsyncGroq

from app.core import config

log = logging.getLogger("urimai.llm")


class LLMError(RuntimeError):
    pass


_client: AsyncGroq | None = None


def client() -> AsyncGroq:
    global _client
    if not config.GROQ_API_KEY:
        raise LLMError("GROQ_API_KEY is not set")
    if _client is None:
        _client = AsyncGroq(api_key=config.GROQ_API_KEY, timeout=config.LLM_TIMEOUT_S, max_retries=0)
    return _client


def available() -> bool:
    return bool(config.GROQ_API_KEY)


MAX_RATE_LIMIT_WAIT_S = 3.0
_RETRY_IN = re.compile(r"try again in ([\d.]+)(ms|s)")


def _rate_limit_wait(err: str) -> float | None:
    """Seconds Groq asks us to wait on a 429, if stated."""
    if "429" not in err and "rate_limit" not in err:
        return None
    m = _RETRY_IN.search(err)
    if not m:
        return None
    n = float(m.group(1))
    return n / 1000 if m.group(2) == "ms" else n


async def _chat(messages: list[dict], *, json_mode: bool, max_tokens: int, temperature: float) -> str:
    """Try the primary model, then each fallback. Groq rate limits are per model, so spreading across
    models multiplies throughput. A short 429 ("try again in 0.8s") is waited out once on the same model."""
    models = [config.LLM_MODEL] + [m for m in config.LLM_FALLBACK_MODELS if m != config.LLM_MODEL]
    last: LLMError | None = None
    for model in models:
        for attempt in (1, 2):
            try:
                return await _chat_once(model, messages, json_mode=json_mode, max_tokens=max_tokens,
                                        temperature=temperature)
            except LLMError as e:
                last = e
                if "401" in str(e):
                    raise
                wait = _rate_limit_wait(str(e))
                if attempt == 1 and wait is not None and wait <= MAX_RATE_LIMIT_WAIT_S:
                    log.info("%s rate-limited; waiting %.1fs", model, wait)
                    await asyncio.sleep(wait + 0.2)
                    continue
                log.warning("%s failed (%s); trying next model", model, str(e)[:160])
                break
    raise last or LLMError("no model available")


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


async def _chat_once(model: str, messages: list[dict], *, json_mode: bool, max_tokens: int, temperature: float) -> str:
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_completion_tokens=max_tokens,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if "gpt-oss" in model:
        extra = {"reasoning_effort": config.LLM_REASONING_EFFORT}
    elif "qwen" in model:
        extra = {"reasoning_format": "hidden"}
    else:
        extra = {}
    try:
        resp = await asyncio.wait_for(
            client().chat.completions.create(**kwargs, extra_body=extra or None),
            timeout=config.LLM_TIMEOUT_S,
        )
    except asyncio.TimeoutError as e:
        raise LLMError("LLM timeout") from e
    except LLMError:
        raise
    except Exception as e:  # network, rate limit, bad request...
        raise LLMError(f"{type(e).__name__}: {e}") from e
    content = _strip_think(resp.choices[0].message.content or "")
    if not content:
        raise LLMError("empty LLM response")
    u = getattr(resp, "usage", None)
    if u:
        log.info("%s tokens: prompt=%s completion=%s", model, u.prompt_tokens, u.completion_tokens)
    return content


async def complete_json(system: str, user: str, max_tokens: int = 2000) -> dict:
    text = await _chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                       json_mode=True, max_tokens=max_tokens, temperature=0.1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise LLMError(f"non-JSON response: {text[:200]}")


async def complete_text(system: str, user: str, max_tokens: int = 1200) -> str:
    return await _chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                       json_mode=False, max_tokens=max_tokens, temperature=0.4)


async def transcribe(audio: bytes, filename: str, lang: str | None) -> str:
    kwargs = dict(file=(filename, audio), model=config.STT_MODEL, response_format="json", temperature=0.0)
    if lang in ("ta", "hi", "en"):
        kwargs["language"] = lang
    try:
        resp = await asyncio.wait_for(client().audio.transcriptions.create(**kwargs), timeout=30)
    except asyncio.TimeoutError as e:
        raise LLMError("STT timeout") from e
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"{type(e).__name__}: {e}") from e
    return (getattr(resp, "text", "") or "").strip()
