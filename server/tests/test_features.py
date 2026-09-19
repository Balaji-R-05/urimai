"""Feature tests: tap-friendly questions (#4) and scheme Q&A (#1). No network needed."""
import pytest
from fastapi.testclient import TestClient

from app.agents import answerer, extractor, llm
from app.core import config
from app.engine.planner import question_payload
from app.main import app
from app.services import orchestrator


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    return TestClient(app)


# ---------- #4 buttons ----------

def test_occupation_has_buttons_in_tamil():
    q = question_payload("occupation", "ta")
    assert q["input_type"] == "enum"
    labels = [o["label"] for o in q["options"]]
    assert "விவசாயக் கூலித் தொழிலாளி" in labels and "தெரியாது" in labels
    assert len(q["options"]) <= 10


def test_disability_percent_has_range_buttons():
    q = question_payload("disability_percent", "en")
    assert q["input_type"] == "enum"
    assert [o["value"] for o in q["options"]][:3] == [30, 60, 85]


# a profile where only disability decides the disability pension (igndps)
BASE = {"age": 50, "gender": "male", "state": "TN", "annual_family_income": 50000, "has_bpl_ration_card": True,
        "occupation": "daily_wage_labourer", "marital_status": "married", "residence": "urban",
        "has_pucca_house": True, "is_epfo_member": False, "owns_house": True, "has_electricity_connection": True,
        "wants_to_start_business": False, "children": [], "caste_category": "bc"}


def _session(sid):
    from app.core.session import Session
    return Session(id=sid, profile=dict(BASE))


@pytest.mark.anyio
async def test_disability_asks_yes_no_first_and_no_resolves_pension(client):
    s = _session("dis-no")
    r = await orchestrator.answer(s, "age", 50, "en")
    assert r["next_question"]["field"] == "has_disability"  # yes/no gate, not the percentage
    assert r["next_question"]["input_type"] == "bool"
    r = await orchestrator.answer(s, "has_disability", False, "en")
    assert r["profile"]["disability_percent"] == 0
    assert any(x["scheme_id"] == "igndps" for x in r["results"]["not_eligible"])
    assert r["next_question"] is None or r["next_question"]["field"] != "disability_percent"


@pytest.mark.anyio
async def test_disability_yes_then_range_button(client):
    s = _session("dis-yes")
    await orchestrator.answer(s, "age", 50, "en")
    r = await orchestrator.answer(s, "has_disability", True, "en")
    assert r["next_question"]["field"] == "disability_percent"
    assert r["next_question"]["input_type"] == "enum"
    r = await orchestrator.answer(s, "disability_percent", 85, "en")
    assert any(x["scheme_id"] == "igndps" for x in r["results"]["likely"])
    view = {p["field"]: p["display"] for p in r["profile_view"]}
    assert view["disability_percent"] == "80% or more"


@pytest.mark.anyio
async def test_ignored_gate_does_not_fall_through_to_percentage(client):
    s = _session("dis-ignored")
    s.asked["has_disability"] = 2
    r = await orchestrator.answer(s, "age", 50, "en")
    assert r["next_question"] is None or r["next_question"]["field"] not in ("has_disability", "disability_percent")


# ---------- #1 scheme Q&A ----------

@pytest.mark.anyio
async def test_scheme_question_uses_template_when_llm_fails(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)

    async def fake_extract(*a, **k):
        return [], {"scheme_ids": ["kmut"], "topic": "documents"}

    async def boom(**k):
        raise llm.LLMError("down")

    monkeypatch.setattr(extractor, "extract", fake_extract)
    monkeypatch.setattr(answerer, "answer", boom)
    from app.core.session import Session
    s = Session(id="qa")
    r = await orchestrator.chat(s, "KMUT-க்கு என்ன ஆவணம் வேணும்?", "ta")
    assert r["answered_schemes"] == ["kmut"]
    assert "கலைஞர் மகளிர் உரிமைத் தொகை" in r["reply"]
    assert "ஆதார் அட்டை" in r["reply"]           # documents come from the catalogue record
    assert r["next_question"]["text"] in r["reply"]  # interview continues after the answer


# ---------- off-topic reply to a question ----------

@pytest.mark.anyio
async def test_off_topic_reply_repeats_question_without_using_a_try(monkeypatch):
    from app.agents import responder
    from app.core.session import Session
    monkeypatch.setattr(llm, "available", lambda: True)
    seen = []

    async def nothing_extracted(*a, **k):
        return [], None

    async def fake_respond(**k):
        seen.append(k)
        return f"That's nice! Sorry, one more thing. {k['next_question']}"

    monkeypatch.setattr(extractor, "extract", nothing_extracted)
    monkeypatch.setattr(responder, "respond", fake_respond)
    s = Session(id="ot")
    r = await orchestrator.answer(s, "gender", "female", "en")
    field = r["next_question"]["field"]  # the opening question: the first thing a new user is asked
    tries = s.asked[field]
    seen.clear()
    for _ in range(3):  # more off-topic replies than the two tries a question gets
        r = await orchestrator.chat(s, "today's weather is good", "en")
        assert r["next_question"]["field"] == field
        assert r["reply"].startswith("That's nice!")
    assert s.asked[field] == tries
    assert all(k["off_topic"] for k in seen) and not r["learned"]


@pytest.mark.anyio
async def test_off_topic_template_when_llm_reply_fails(monkeypatch):
    from app.agents import responder
    from app.core.session import Session
    monkeypatch.setattr(llm, "available", lambda: True)

    async def nothing_extracted(*a, **k):
        return [], None

    async def boom(**k):
        raise llm.LLMError("down")

    monkeypatch.setattr(extractor, "extract", nothing_extracted)
    monkeypatch.setattr(responder, "respond", boom)
    s = Session(id="ot2")
    q = (await orchestrator.answer(s, "gender", "female", "ta"))["next_question"]
    r = await orchestrator.chat(s, "இன்னைக்கு வானிலை நல்லா இருக்கு", "ta")
    assert r["reply"].startswith("பகிர்ந்ததற்கு நன்றி") and r["reply"].endswith(q["text"])


@pytest.mark.anyio
async def test_real_answer_is_not_off_topic(monkeypatch):
    from app.core.session import Session
    monkeypatch.setattr(llm, "available", lambda: True)
    s = Session(id="ot3")
    await orchestrator.answer(s, "gender", "female", "en")
    q = (await orchestrator.answer(s, "age", 30, "en"))["next_question"]
    assert q["field"] != "opening"
    value = q["options"][0]["value"] if q["options"] else {"state": "TN", "district": "Madurai"}[q["field"]]

    async def extracted(*a, **k):
        return [{"field": q["field"], "value": value, "quote": "x", "confidence": 0.9}], None

    monkeypatch.setattr(extractor, "extract", extracted)
    r = await orchestrator.chat(s, "my answer", "en")
    assert r["next_question"] is None or r["next_question"]["field"] != q["field"]
    assert not any(t.get("detail", {}).get("repeat") for t in r["trace"])


@pytest.fixture
def anyio_backend():
    return "asyncio"
