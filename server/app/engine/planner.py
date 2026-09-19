"""Next-question planner: pick the unknown field that resolves the most value."""
from __future__ import annotations

import math

from app.domain.fields import DONT_KNOW, FIELD_PRIORITY, FIELDS, NO, UI, YES, tr
from app.engine.rules import F, eval_condition

CORE_FIELDS = ("age", "gender", "district", "state", "occupation", "annual_family_income", "marital_status")
BUTTON_MAX = 10


def scheme_weight(scheme: dict) -> float:
    value = scheme.get("benefit", {}).get("annual_cash_value_inr", 0) or 0
    w = 1 + math.log10(1 + value)
    if set(scheme.get("category", [])) & {"health", "housing"}:
        w += 2
    return w


def _allowed(field: str, facts: dict) -> bool:
    """A question is skipped only if a KNOWN fact rules it out (e.g. don't ask a widow of 42 about pregnancy)."""
    return all(eval_condition(facts, c) != F for c in FIELDS.get(field, {}).get("ask_if", []))


def next_field(results: list[dict], schemes_by_id: dict, facts: dict,
               asked: dict[str, int], skipped: set[str]) -> str | None:
    known_core = sum(1 for f in CORE_FIELDS if facts.get(f) is not None)
    if known_core < 2 and asked.get("opening", 0) == 0:
        return "opening"

    score: dict[str, float] = {}
    for r in results:
        if r["status"] != "need_info" or not r["missing_fields"]:
            continue
        w = scheme_weight(schemes_by_id[r["scheme_id"]])
        share = w / len(r["missing_fields"])
        for f in r["missing_fields"]:
            score[f] = score.get(f, 0.0) + share

    def blocked_by_gate(f: str) -> bool:
        gate = FIELDS.get(f, {}).get("ask_first")
        if not gate:
            return False
        ignored = facts.get(gate) is None and asked.get(gate, 0) >= 2  # asked twice, never answered
        return gate in skipped or facts.get(gate) is False or ignored

    candidates = [
        f for f in score
        if f in FIELDS and f not in skipped and asked.get(f, 0) < 2 and _allowed(f, facts) and not blocked_by_gate(f)
    ]
    if not candidates:
        return None
    prio = {f: i for i, f in enumerate(FIELD_PRIORITY)}
    candidates.sort(key=lambda f: (-round(score[f], 6), prio.get(f, 999)))
    best = candidates[0]
    # e.g. ask "Do you have a disability?" (yes/no) before "What percentage?"
    gate = FIELDS[best].get("ask_first")
    if gate and facts.get(gate) is None and asked.get(gate, 0) < 2:
        return gate
    return best


def question_payload(field: str | None, lang: str) -> dict | None:
    if field is None:
        return None
    if field == "opening":
        return {"field": "opening", "text": tr(UI["opening"], lang), "input_type": "text", "options": []}
    meta = FIELDS[field]
    t = meta["type"]
    options: list[dict] = []
    input_type = "text"
    if t == "bool":
        input_type = "bool"
        options = [
            {"value": True, "label": tr(YES, lang)},
            {"value": False, "label": tr(NO, lang)},
            {"value": None, "label": tr(DONT_KNOW, lang), "skip": True},
        ]
    elif t == "enum" and meta.get("buttons"):
        keys = meta.get("button_subset") or list(meta["options"])
        if len(keys) <= BUTTON_MAX:
            input_type = "enum"
            options = [{"value": k, "label": tr(meta["options"][k], lang)} for k in keys]
            options.append({"value": None, "label": tr(DONT_KNOW, lang), "skip": True})
    elif t in ("int", "float") and meta.get("choices"):
        input_type = "enum"
        options = [{"value": c["value"], "label": tr(c["label"], lang)} for c in meta["choices"]]
        options.append({"value": None, "label": tr(DONT_KNOW, lang), "skip": True})
    elif t in ("int", "float"):
        input_type = "number"
    return {"field": field, "text": tr(meta["q"], lang), "input_type": input_type, "options": options}
