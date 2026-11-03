"""
Offline accuracy check for the extractor agent (app/agents/extractor.py) against real Groq calls.

Not a pytest test: it costs real API calls and the LLM is non-deterministic, so it's run by hand
to measure/track extraction accuracy, not to gate CI. Run from server/:

    python -m app.agents.eval_extractor

Loads server/data/extractor_eval.json: each case gives a message (ta/en/hi/Tanglish) and the
profile fields and/or scheme question the extractor should produce. Runs the real extract() call,
then the same normalise.apply_updates() the orchestrator uses, so results reflect exactly what a
user would get -- then reports per-case and per-field pass/fail plus overall precision.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.agents import extractor, llm
from app.core import config
from app.nlp import numerals
from app.nlp.normalise import apply_updates

CASES_PATH = Path(__file__).resolve().parents[2] / "data" / "extractor_eval.json"


async def _run_case(case: dict) -> dict:
    profile = dict(case.get("profile") or {})
    message = numerals.to_digits(case["message"])
    try:
        updates, question = await extractor.extract(
            message, case.get("history") or [], case.get("last_field"), profile
        )
    except llm.LLMError as e:
        return {
            "id": case["id"],
            "lang": case.get("lang", "?"),
            "fields": [],
            "question_ok": False,
            "question": None,
            "error": str(e),
        }

    learned, changes = apply_updates(profile, updates, 1, {})
    extracted = {e["field"]: e["new"] for e in learned + changes}

    fields = [
        {"field": f, "want": want, "got": extracted.get(f), "ok": extracted.get(f) == want}
        for f, want in (case.get("expect_profile") or {}).items()
    ]

    expect_q = case.get("expect_question")
    if "expect_question" not in case:
        question_ok = None  # not asserted for this case
    elif expect_q is None:
        question_ok = question is None
    elif question is None:
        question_ok = False
    else:
        ids_ok = not expect_q.get("scheme_ids_any") or any(
            i in question["scheme_ids"] for i in expect_q["scheme_ids_any"]
        )
        question_ok = ids_ok and question["topic"] == expect_q.get("topic", question["topic"])

    return {
        "id": case["id"],
        "lang": case.get("lang", "?"),
        "fields": fields,
        "question_ok": question_ok,
        "question": question,
        "error": None,
    }


async def main() -> int:
    if not config.GROQ_API_KEY:
        print(
            "GROQ_API_KEY is not set -- this eval calls the real Groq API, nothing to run without it."
        )
        return 1

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    total_fields = correct_fields = 0
    total_q = correct_q = 0
    failed_cases = 0

    for case in cases:
        r = await _run_case(case)
        bad_fields = [f for f in r["fields"] if not f["ok"]]
        total_fields += len(r["fields"])
        correct_fields += len(r["fields"]) - len(bad_fields)
        if r["question_ok"] is not None:
            total_q += 1
            correct_q += int(r["question_ok"])

        ok = not r["error"] and not bad_fields and r["question_ok"] is not False
        failed_cases += not ok
        print(f"[{'PASS' if ok else 'FAIL'}] {r['id']} ({r['lang']})")
        if r["error"]:
            print(f"    error: {r['error']}")
        for f in bad_fields:
            print(f"    field {f['field']}: want {f['want']!r}, got {f['got']!r}")
        if r["question_ok"] is False:
            print(f"    question: expected a scheme question, got {r['question']!r}")

    print()
    print(f"Cases:     {len(cases) - failed_cases}/{len(cases)} passed")
    if total_fields:
        print(
            f"Fields:    {correct_fields}/{total_fields} correct ({correct_fields / total_fields:.0%})"
        )
    if total_q:
        print(f"Questions: {correct_q}/{total_q} correct ({correct_q / total_q:.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
