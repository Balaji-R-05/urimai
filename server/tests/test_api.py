"""API tests with the LLM switched off: proves the engine + template fallback path works end to end."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.main import app

PERSONA_A = json.loads((Path(__file__).parent / "personas.json").read_text(encoding="utf-8"))[0]["profile"]


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "")


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health").json()
    assert r["ok"] and r["llm"] == "down" and r["schemes"] >= 25


def test_evaluate_form_mode_tamil(client):
    r = client.post("/api/evaluate", json={"profile": PERSONA_A, "lang": "ta"}).json()
    likely = {x["scheme_id"] for x in r["results"]["likely"]}
    assert {"kmut", "ignwps", "cmchis"} <= likely
    assert r["summary"]["annual_cash_value_inr"] == 14400  # kmut/ignwps choose-one: count the larger
    assert any(d["doc"] == "aadhaar" for d in r["documents"])
    assert "அரசுத் துறை" in r["disclaimer"]


def test_chat_without_llm_asks_opening(client):
    r = client.post("/api/chat", json={"session_id": "t1", "message": "hello", "lang": "ta", "channel": "telegram"}).json()
    assert r["next_question"]["field"] == "opening"
    assert r["reply"]


def test_answer_flow_and_skip(client):
    sid = "t2"
    client.post("/api/session/reset", json={"session_id": sid})
    for field, value in [("age", 42), ("gender", "female"), ("state", "TN"), ("occupation", "agri_labourer")]:
        r = client.post("/api/answer", json={"session_id": sid, "field": field, "value": value, "lang": "en"}).json()
    assert r["profile"]["age"] == 42
    nq = r["next_question"]
    assert nq and nq["field"] != "opening"
    r2 = client.post("/api/answer", json={"session_id": sid, "field": nq["field"], "skip": True, "lang": "en"}).json()
    assert r2["next_question"] is None or r2["next_question"]["field"] != nq["field"]


def test_bool_question_has_buttons(client):
    sid = "t3"
    for field, value in [("age", 30), ("gender", "female"), ("state", "TN"), ("annual_family_income", 100000),
                         ("is_pregnant", True)]:
        r = client.post("/api/answer", json={"session_id": sid, "field": field, "value": value}).json()
    nq = r["next_question"]
    if nq and nq["input_type"] == "bool":
        assert [o["value"] for o in nq["options"]][:2] == [True, False]


def test_correction_is_reported(client):
    sid = "t4"
    client.post("/api/answer", json={"session_id": sid, "field": "age", "value": 42})
    r = client.post("/api/answer", json={"session_id": sid, "field": "age", "value": 38}).json()
    assert r["changes"] and r["changes"][0]["field"] == "age"


def test_unknown_field_rejected(client):
    assert client.post("/api/answer", json={"session_id": "x", "field": "aadhaar", "value": "1"}).status_code == 400
