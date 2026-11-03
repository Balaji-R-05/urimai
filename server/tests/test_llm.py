"""Regression tests for the Groq wrapper's fallback/retry logic and JSON recovery."""

import pytest
from app.agents import llm
from app.core import config


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content, usage=None):
        self.choices = [FakeChoice(content)]
        self.usage = usage


class FakeClient:
    """Stands in for AsyncGroq; `handler` plays the role of the real API call."""

    def __init__(self, handler):
        class _Completions:
            async def create(_self, **kwargs):
                return await handler(**kwargs)

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def _install_client(monkeypatch, handler):
    monkeypatch.setattr(llm, "client", lambda: FakeClient(handler))


# ---------- _rate_limit_wait ----------


def test_rate_limit_wait_parses_seconds():
    assert llm._rate_limit_wait("Error 429: rate_limit_exceeded. try again in 0.8s") == 0.8


def test_rate_limit_wait_parses_milliseconds():
    assert llm._rate_limit_wait("429 rate_limit try again in 800ms") == 0.8


def test_rate_limit_wait_none_without_retry_hint():
    assert llm._rate_limit_wait("429 rate_limit_exceeded, no retry hint given") is None


def test_rate_limit_wait_none_for_unrelated_errors():
    assert llm._rate_limit_wait("500 internal server error") is None


# ---------- _strip_think ----------


def test_strip_think_removes_reasoning_block():
    assert llm._strip_think("<think>reasoning...</think>answer") == "answer"


def test_strip_think_leaves_plain_text_untouched():
    assert llm._strip_think("plain answer") == "plain answer"


# ---------- _chat: fallback across models ----------


@pytest.mark.anyio
async def test_chat_falls_back_to_next_model_on_failure(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODEL", "model-a")
    monkeypatch.setattr(config, "LLM_FALLBACK_MODELS", ["model-b"])
    seen = []

    async def handler(**kwargs):
        seen.append(kwargs["model"])
        if kwargs["model"] == "model-a":
            raise RuntimeError("model-a is overloaded")
        return FakeResponse("ok from model-b")

    _install_client(monkeypatch, handler)
    out = await llm._chat(
        [{"role": "user", "content": "hi"}], json_mode=False, max_tokens=10, temperature=0.1
    )
    assert out == "ok from model-b"
    assert seen == ["model-a", "model-b"]


@pytest.mark.anyio
async def test_chat_raises_immediately_on_401_without_trying_fallback(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODEL", "model-a")
    monkeypatch.setattr(config, "LLM_FALLBACK_MODELS", ["model-b"])
    seen = []

    async def handler(**kwargs):
        seen.append(kwargs["model"])
        raise RuntimeError("401 invalid api key")

    _install_client(monkeypatch, handler)
    with pytest.raises(llm.LLMError, match="401"):
        await llm._chat(
            [{"role": "user", "content": "hi"}], json_mode=False, max_tokens=10, temperature=0.1
        )
    assert seen == ["model-a"]  # auth failure must not burn the fallback chain


@pytest.mark.anyio
async def test_chat_waits_out_a_short_rate_limit_on_the_same_model(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODEL", "model-a")
    monkeypatch.setattr(config, "LLM_FALLBACK_MODELS", [])
    calls = []

    async def handler(**kwargs):
        calls.append(kwargs["model"])
        if len(calls) == 1:
            raise RuntimeError("429 rate_limit_exceeded, try again in 0.01s")
        return FakeResponse("ok")

    _install_client(monkeypatch, handler)
    slept = []

    async def fake_sleep(s):
        slept.append(s)

    monkeypatch.setattr(llm.asyncio, "sleep", fake_sleep)

    out = await llm._chat(
        [{"role": "user", "content": "hi"}], json_mode=False, max_tokens=10, temperature=0.1
    )
    assert out == "ok"
    assert calls == ["model-a", "model-a"]  # retried the same model, no fallback needed
    assert slept == [pytest.approx(0.21)]


@pytest.mark.anyio
async def test_chat_raises_last_error_when_every_model_fails(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODEL", "model-a")
    monkeypatch.setattr(config, "LLM_FALLBACK_MODELS", ["model-b"])

    async def handler(**kwargs):
        raise RuntimeError(f"{kwargs['model']} is down")

    _install_client(monkeypatch, handler)
    with pytest.raises(llm.LLMError, match="model-b is down"):
        await llm._chat(
            [{"role": "user", "content": "hi"}], json_mode=False, max_tokens=10, temperature=0.1
        )


# ---------- complete_json ----------


@pytest.mark.anyio
async def test_complete_json_parses_clean_json(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODEL", "model-a")
    monkeypatch.setattr(config, "LLM_FALLBACK_MODELS", [])

    async def handler(**kwargs):
        return FakeResponse('{"a": 1}')

    _install_client(monkeypatch, handler)
    assert await llm.complete_json("sys", "user") == {"a": 1}


@pytest.mark.anyio
async def test_complete_json_extracts_json_embedded_in_extra_text(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODEL", "model-a")
    monkeypatch.setattr(config, "LLM_FALLBACK_MODELS", [])

    async def handler(**kwargs):
        return FakeResponse('Sure, here it is: {"a": 1} -- hope that helps!')

    _install_client(monkeypatch, handler)
    assert await llm.complete_json("sys", "user") == {"a": 1}


@pytest.mark.anyio
async def test_complete_json_raises_on_non_json_response(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODEL", "model-a")
    monkeypatch.setattr(config, "LLM_FALLBACK_MODELS", [])

    async def handler(**kwargs):
        return FakeResponse("not json at all")

    _install_client(monkeypatch, handler)
    with pytest.raises(llm.LLMError):
        await llm.complete_json("sys", "user")


@pytest.fixture
def anyio_backend():
    return "asyncio"
