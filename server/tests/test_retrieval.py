"""Retrieval wiring for scheme Q&A: merge rules (pure) and the orchestrator path with the search stubbed.
The ranking quality itself is measured by `python -m app.retrieval.demo` (needs the models)."""
import pytest

from app.agents import answerer, extractor, llm
from app.core import config
from app.core.session import Session
from app.retrieval import service as retrieval
from app.services import orchestrator


def hit(scheme, section="overview", score=0.9, reranked=True):
    return {"scheme_id": scheme, "section": section, "score": score, "reranked": reranked,
            "rerank_score": score if reranked else None, "rrf": 0.03, "dense_rank": 1, "bm25_rank": 2,
            "chunk": f"{scheme} | {section}", "context": f"{scheme} {section} text"}


def test_specific_question_keeps_extractor_ids():
    q = retrieval.merge_question({"scheme_ids": ["kmut"], "topic": "documents"},
                                 [hit("pmkvy", "documents"), hit("kmut", "documents")])
    assert q["scheme_ids"] == ["kmut"] and q["topic"] == "documents" and q["source"] == "extractor"
    assert [p["scheme_id"] for p in q["passages"]] == ["kmut"]  # passages only for answered schemes


def test_broad_question_uses_retrieval_and_refines_topic():
    q = retrieval.merge_question({"scheme_ids": [], "topic": "general"},
                                 [hit("pmay_g", "how_to_apply"), hit("pmay_u"), hit("apy", score=0.1)])
    assert q["scheme_ids"] == ["pmay_g", "pmay_u"]   # apy is below RETRIEVAL_MIN_SCORE
    assert q["topic"] == "how_to_apply" and q["source"] == "retrieval"


def test_broad_question_merges_both_sources():
    q = retrieval.merge_question({"scheme_ids": ["kalaignar_kanavu_illam"], "topic": "general"},
                                 [hit("pmay_g"), hit("pmay_u"), hit("kalaignar_kanavu_illam")])
    assert q["scheme_ids"] == ["pmay_g", "pmay_u", "kalaignar_kanavu_illam"] and q["source"] == "both"


def test_without_reranker_only_top_hit_is_trusted():
    q = retrieval.merge_question({"scheme_ids": [], "topic": "general"},
                                 [hit("ignwps", score=0.03, reranked=False), hit("apy", score=0.02, reranked=False)])
    assert q["scheme_ids"] == ["ignwps"]


def test_no_ids_anywhere_drops_the_question():
    assert retrieval.merge_question({"scheme_ids": [], "topic": "general"}, None) is None
    assert retrieval.merge_question({"scheme_ids": [], "topic": "general"}, [hit("apy", score=0.1)]) is None


@pytest.mark.anyio
async def test_disabled_retrieval_returns_none():
    assert await retrieval.search("housing") is None


@pytest.mark.anyio
async def test_orchestrator_answers_schemes_found_by_retrieval(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(config, "RETRIEVAL_ENABLED", True)

    async def fake_extract(*a, **k):  # LLM saw a question but could not name a scheme
        return [], {"scheme_ids": [], "topic": "general"}

    seen = {}

    async def fake_answer(**k):
        seen.update(k)
        return "grounded answer"

    monkeypatch.setattr(extractor, "extract", fake_extract)
    monkeypatch.setattr(answerer, "answer", fake_answer)
    monkeypatch.setattr(retrieval, "_search", lambda text, state=None: [hit("pmay_g"), hit("kalaignar_kanavu_illam")])
    r = await orchestrator.chat(Session(id="rq"), "any help to build a house?", "en")
    assert r["answered_schemes"] == ["pmay_g", "kalaignar_kanavu_illam"]
    assert r["reply"].startswith("grounded answer")
    assert [p["scheme_id"] for p in seen["passages"]] == ["pmay_g", "kalaignar_kanavu_illam"]
    step = next(t for t in r["trace"] if t["step"] == "retrieve")
    assert step["detail"]["source"] == "retrieval" and step["detail"]["hits"][0]["rerank"] == 0.9


@pytest.mark.anyio
async def test_retrieval_failure_falls_back_to_extractor(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(config, "RETRIEVAL_ENABLED", True)

    async def fake_extract(*a, **k):
        return [], {"scheme_ids": ["kmut"], "topic": "general"}

    async def boom(**k):
        raise llm.LLMError("down")

    def broken(text, state=None):
        raise RuntimeError("model missing")

    monkeypatch.setattr(extractor, "extract", fake_extract)
    monkeypatch.setattr(answerer, "answer", boom)
    monkeypatch.setattr(retrieval, "_search", broken)
    r = await orchestrator.chat(Session(id="rf"), "tell me about KMUT", "en")
    assert r["answered_schemes"] == ["kmut"]


@pytest.fixture
def anyio_backend():
    return "asyncio"
