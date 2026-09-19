"""Three-valued (Kleene) rule engine.

T = condition met, F = not met, U = unknown (field missing from the profile).
The LLM never touches this module: eligibility is decided here and only here.
eligibility.other holds requirements that can't be checked from the profile: they are listed for the user
("manual" checks) but never change the status.
"""
from __future__ import annotations

from app.domain.fields import DERIVED, EDUCATION_ORDER, UI, UNORGANISED, tr
from app.domain.formatting import condition_text, value_display

T, F, U = "T", "F", "U"
OUTCOME = {T: "pass", F: "fail", U: "unknown"}
STATUS = {T: "likely", U: "need_info", F: "not_eligible"}


def _expand(values):
    out = []
    for v in values:
        if v == "@UNORGANISED":
            out.extend(UNORGANISED)
        else:
            out.append(v)
    return out


def _cmp_value(field: str, v):
    if field == "education_level" and isinstance(v, str):
        return EDUCATION_ORDER.index(v) if v in EDUCATION_ORDER else -1
    return v


def eval_condition(facts: dict, cond: dict) -> str:
    field, op, want = cond["field"], cond["op"], cond.get("value")
    have = facts.get(field)
    if have is None:
        return U
    try:
        if op == "is_true":
            ok = have is True
        elif op == "is_false":
            ok = have is False
        elif op == "eq":
            ok = have == want
        elif op == "ne":
            ok = have != want
        elif op == "in":
            ok = have in _expand(want)
        elif op == "not_in":
            ok = have not in _expand(want)
        else:
            h = _cmp_value(field, have)
            if op == "between":
                lo, hi = (_cmp_value(field, x) for x in want)
                ok = lo <= h <= hi
            else:
                w = _cmp_value(field, want)
                ok = {"lt": h < w, "lte": h <= w, "gt": h > w, "gte": h >= w}[op]
    except (TypeError, KeyError):
        return U
    return T if ok else F


def neg(v: str) -> str:
    return {T: F, F: T, U: U}[v]


def k_all(vals) -> str:
    vals = list(vals)
    if F in vals:
        return F
    if U in vals:
        return U
    return T


def k_any(vals) -> str:
    vals = list(vals)
    if not vals:
        return T
    if T in vals:
        return T
    if U in vals:
        return U
    return F


def _source_field(field: str) -> str:
    return DERIVED.get(field, {}).get("source", field)


def evaluate_scheme(facts: dict, scheme: dict, lang: str = "en") -> dict:
    elig = scheme["eligibility"]
    checks: list[dict] = []
    missing: list[str] = []

    def add_check(cond, value, negate=False, group=None):
        field = cond["field"]
        check = {
            "text": condition_text(cond, lang, negate=negate),
            "field": field,
            "outcome": OUTCOME[value],
        }
        # show the user's own value where it adds information: numeric ranges, or any failed check
        informative = cond["op"] in ("between", "gte", "gt", "lte", "lt") or value == F
        if (informative and facts.get(field) is not None and field not in DERIVED
                and cond["op"] not in ("is_true", "is_false")):
            check["yours"] = value_display(field, facts[field], lang)
        if group:
            check["group"] = group
        checks.append(check)

    all_vals = []
    for cond in elig.get("all", []):
        v = eval_condition(facts, cond)
        all_vals.append(v)
        add_check(cond, v)
        if v == U:
            missing.append(_source_field(cond["field"]))

    any_conds = elig.get("any", [])
    any_vals = [eval_condition(facts, c) for c in any_conds]
    any_result = k_any(any_vals)
    group = tr(UI["one_of"], lang) if any_conds else None
    for cond, v in zip(any_conds, any_vals):
        add_check(cond, v, group=group)
        if any_result == U and v == U:
            missing.append(_source_field(cond["field"]))

    none_vals = []
    for cond in elig.get("none", []):
        v = neg(eval_condition(facts, cond))
        none_vals.append(v)
        add_check(cond, v, negate=True)
        if v == U:
            missing.append(_source_field(cond["field"]))

    for text in elig.get("other", []):
        checks.append({"text": tr(text, lang), "field": None, "outcome": "manual"})

    overall = k_all([k_all(all_vals), any_result, k_all(none_vals)])
    fail = next((c for c in checks if c["outcome"] == "fail" and not c.get("group")), None)
    if fail is None and any_result == F:
        fail = {"text": group + ": " + " / ".join(c["text"] for c in checks if c.get("group"))}
    fail_reason = None
    if overall == F and fail:
        fail_reason = fail["text"] + (f" ({tr(UI['you'], lang)}: {fail['yours']})" if fail.get("yours") else "")

    return {
        "scheme_id": scheme["id"],
        "status": STATUS[overall],
        "checks": checks,
        "missing_fields": list(dict.fromkeys(missing)) if overall == U else [],
        "fail_reason": fail_reason,
    }


def evaluate_all(facts: dict, schemes: list[dict], lang: str = "en") -> list[dict]:
    results = [evaluate_scheme(facts, s, lang) for s in schemes]
    likely = {r["scheme_id"] for r in results if r["status"] == "likely"}
    by_id = {s["id"]: s for s in schemes}
    # symmetric mutual-exclusion among likely schemes
    excl: dict[str, set[str]] = {sid: set() for sid in by_id}
    for s in schemes:
        for other in s.get("mutually_exclusive_with", []):
            if other in excl:
                excl[s["id"]].add(other)
                excl[other].add(s["id"])
    for r in results:
        r["conflicts_with"] = sorted(excl[r["scheme_id"]] & likely) if r["status"] == "likely" else []
    return results
