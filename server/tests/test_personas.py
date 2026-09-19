"""Persona suite: every (persona, scheme, expected status) row is one check. The count goes on the slide."""
import json
from pathlib import Path

import pytest

from app.catalogue.loader import load_schemes
from app.engine.derive import derive
from app.engine.planner import next_field
from app.engine.rules import evaluate_all
from app.engine.summary import build_hints

PERSONAS = json.loads((Path(__file__).parent / "personas.json").read_text(encoding="utf-8"))
SCHEMES = load_schemes()
BY_ID = {s["id"]: s for s in SCHEMES}

ROWS = [
    (p["id"], sid, status)
    for p in PERSONAS
    for status, ids in p["expect"].items()
    for sid in ids
]


def _run(persona):
    facts, _ = derive(persona["profile"])
    return facts, {r["scheme_id"]: r for r in evaluate_all(facts, SCHEMES)}


@pytest.mark.parametrize("pid,scheme_id,status", ROWS)
def test_persona_status(pid, scheme_id, status):
    persona = next(p for p in PERSONAS if p["id"] == pid)
    assert scheme_id in BY_ID, f"unknown scheme {scheme_id}"
    _, results = _run(persona)
    r = results[scheme_id]
    assert r["status"] == status, f"{pid}/{scheme_id}: got {r['status']} ({r['fail_reason'] or r['missing_fields']})"


@pytest.mark.parametrize("persona", [p for p in PERSONAS if p.get("conflicts")], ids=lambda p: p["id"])
def test_persona_conflicts(persona):
    _, results = _run(persona)
    for a, b in persona["conflicts"]:
        assert b in results[a]["conflicts_with"]
        assert a in results[b]["conflicts_with"]


@pytest.mark.parametrize("persona", [p for p in PERSONAS if p.get("first_question_in")], ids=lambda p: p["id"])
def test_persona_first_question(persona):
    facts, results = _run(persona)
    field = next_field(list(results.values()), BY_ID, facts, asked={}, skipped=set())
    assert field in persona["first_question_in"]


@pytest.mark.parametrize("persona", [p for p in PERSONAS if "hints" in p], ids=lambda p: p["id"])
def test_persona_hints(persona):
    facts, _ = derive(persona["profile"])
    assert len(build_hints(facts, "en")) == persona["hints"]


def test_catalogue_loads_and_localizes():
    assert len(SCHEMES) >= 25
    for s in SCHEMES:
        assert s["name"].get("ta"), f"{s['id']} missing Tamil name"
