"""
One-off tool: draft Urimai scheme records from a raw myScheme-style export (free-text
eligibility/benefits/application fields) using an LLM extraction pass against our
structured schema (app/catalogue/schema.py).

This NEVER writes straight into schemes.json or MongoDB. Every record comes out with
verification.status "draft" and is meant to be checked against its official source,
corrected, and promoted to "unverified"/"verified" by a human before
`python -m app.catalogue.seed` ever sees it. The LLM is good at turning prose into a
first-pass structured guess; it is not trusted to get eligibility rules right un-reviewed.

Input shape expected per record (matches the "gov-myscheme-dataset" GitHub export):
    {
      "Scheme Name": ..., "Scheme Slug": ..., "Level": "Central Government" | "State / UT Government",
      "State / UT / Ministry": ..., "Application Mode": ..., "Tags / Categories": ...,
      "Description": ..., "Eligibility Criteria": ..., "Eligibility (General)": ...,
      "Exclusions / Ineligibility": ..., "Benefits": ..., "Application Process": ...,
      "Documents Required": ..., "Frequently Asked Questions (FAQs)": ...,
      "Official Link": ..., "MyScheme URL": ...
    }

Usage:
    cd server
    python -m app.catalogue.import_myscheme <raw.json> --state "Tamil Nadu" --limit 5 --out data/drafts/batch.json
    python -m app.catalogue.import_myscheme <raw.json> --level central --limit 10 --out data/drafts/central.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path

from app.agents import llm
from app.catalogue import schema
from app.core import config
from app.domain.fields import DERIVED, DOC_LABELS, FIELDS, STATE_CODES

log = logging.getLogger("urimai.import_myscheme")

LEVEL_MAP = {"Central Government": "central", "State / UT Government": "state"}


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    s = re.sub(r"_+", "_", s)
    return (s or "scheme")[:63]


def _field_catalogue() -> str:
    """Compact field reference for the prompt: name (type, options/range)."""
    lines = []
    for name, meta in {**FIELDS, **DERIVED}.items():
        if name in DERIVED:
            lines.append(f"- {name}: bool (derived; yes/no only)")
            continue
        if name == "state":
            lines.append(f"- state: enum {{{', '.join(sorted(schema.STATES))}}} (use the 2-letter CODE, not the name)")
            continue
        t = meta["type"]
        if t == "enum":
            lines.append(f"- {name}: enum {{{', '.join(meta['options'])}}}")
        elif t in ("int", "float"):
            lo, hi = meta.get("min"), meta.get("max")
            lines.append(f"- {name}: {t} [{lo}..{hi}]" if lo is not None else f"- {name}: {t}")
        elif t == "bool":
            lines.append(f"- {name}: bool (yes/no)")
        elif t == "children":
            continue  # not directly usable in rules; DERIVED fields stand in for it
        else:
            lines.append(f"- {name}: text")
    return "\n".join(lines)


SYSTEM = f"""
You convert one Indian government welfare scheme's free-text record into a structured JSON object for a
rules-based eligibility checker. Use ONLY facts stated in the record given to you. If something is not
stated, omit that field rather than guessing.

Output a single JSON object with this exact shape (all top-level keys required unless noted optional):
{{
  "name": {{"en": "..."}},
  "category": ["..."],   // 1+ from: {", ".join(sorted(schema.CATEGORIES))}
  "benefit": {{
    "summary": {{"en": "one line: what the person gets"}},
    "annual_cash_value_inr": 0,   // integer, cash per YEAR; 0 if not a cash benefit or unclear
    "cover_highlight": {{"en": "..."}},  // optional, only for non-cash cover (e.g. health insurance amount)
    "frequency": "one_time" | "monthly" | "quarterly" | "annual" | "ongoing"   // optional, only if clear
  }},
  "eligibility": {{
    "all": [{{"field": "...", "op": "...", "value": ...}}],   // every rule must hold
    "any": [...],     // at least one must hold (use sparingly)
    "none": [...],    // none of these may hold (exclusions)
    "other": [{{"en": "requirement text the rules can't express"}}]
  }},
  "documents": ["standard_id", ...],  // from: {", ".join(sorted(DOC_LABELS))} -- or omit anything not in this list
  "application": {{
    "mode": "online" | "offline" | "both",
    "where": {{"en": "..."}},   // optional
    "url": "https://...",       // optional
    "steps": {{"en": ["step 1", "step 2"]}}   // optional
  }},
  "contact": {{"phone": "...", "email": "...", "helpline_hours": {{"en": "..."}}}},  // optional, omit entirely if nothing stated
  "priority_groups": ["..."],  // optional, 0+ from: {", ".join(sorted(schema.PRIORITY_GROUPS))} -- only if the record clearly targets that group
  "confidence_notes": "one sentence: anything you were unsure about or had to infer"
}}

Allowed profile fields for eligibility rules (use ONLY these field names):
{_field_catalogue()}

Allowed ops: eq, ne, in, not_in, lt, lte, gt, gte, between, is_true, is_false.
- is_true / is_false take no "value" and only apply to bool fields.
- "occupation", when using in/not_in, may also use the special value "@UNORGANISED" for any informal-sector job.
- A requirement you cannot map to one of the allowed fields goes in eligibility.other as plain text, not as a
  fabricated field.
- Never invent a field, document id, category, or value outside the lists given above.
- Do NOT add a rule on the "state" field for "must live in this scheme's own state/UT" -- that residency
  requirement is added automatically from the scheme's own record and must not be duplicated here. Only use
  the "state" field for something unusual, e.g. a scheme open to residents of several specific other states.
"""

USER_TEMPLATE = """Scheme record:

Name: {name}
Level: {level}
State / UT / Ministry: {region}
Application mode (source): {mode}
Tags: {tags}

Description:
{description}

Eligibility (general):
{eligibility_general}

Exclusions / ineligibility:
{exclusions}

Benefits:
{benefits}

Application process:
{application_process}

Documents required (source text, may be messy):
{documents}
"""


def _raw_text(v) -> str:
    return (v or "").strip() or "(not stated)"


async def extract_one(raw: dict) -> dict:
    user = USER_TEMPLATE.format(
        name=raw.get("Scheme Name", ""),
        level=raw.get("Level", ""),
        region=raw.get("State / UT / Ministry", ""),
        mode=raw.get("Application Mode", ""),
        tags=raw.get("Tags / Categories", ""),
        description=_raw_text(raw.get("Description")),
        eligibility_general=_raw_text(raw.get("Eligibility (General)") or raw.get("Eligibility Criteria")),
        exclusions=_raw_text(raw.get("Exclusions / Ineligibility")),
        benefits=_raw_text(raw.get("Benefits")),
        application_process=_raw_text(raw.get("Application Process")),
        documents=_raw_text(raw.get("Documents Required")),
    )
    return await llm.complete_json(SYSTEM, user, max_tokens=3000)


def _normalize_other(other: list) -> list[dict]:
    """The weaker fallback models sometimes write plain strings here instead of {"en": ...}."""
    out = []
    for item in other or []:
        if isinstance(item, str):
            out.append({"en": item})
        elif isinstance(item, dict) and item.get("en"):
            out.append(item)
        # silently drop anything else unusable rather than failing the whole scheme over it
    return out


_BOOL_FIELDS = {name for name, meta in FIELDS.items() if meta["type"] == "bool"} | set(DERIVED)


def _normalize_conditions(conditions: list) -> list:
    """The weaker fallback models sometimes write a bool field as eq/ne true/false instead of
    is_true/is_false, which schema.py rejects outright. Rewrite rather than fail the scheme over it."""
    out = []
    for c in conditions or []:
        if isinstance(c, dict) and c.get("field") in _BOOL_FIELDS and c.get("op") in ("eq", "ne"):
            want = bool(c.get("value"))
            if c["op"] == "ne":
                want = not want
            c = {"field": c["field"], "op": "is_true" if want else "is_false"}
        out.append(c)
    return out


def _normalize_documents(docs: list, notes: list[str]) -> list:
    """Drop document ids the fallback models invented outside DOC_LABELS, noting it for review
    instead of discarding the whole scheme over one bad entry."""
    out = []
    for d in docs or []:
        if isinstance(d, str):
            if d in DOC_LABELS:
                out.append(d)
            else:
                notes.append(f"dropped unknown document id {d!r}")
        elif isinstance(d, dict) and d.get("id") and d.get("label"):
            out.append(d)
        else:
            notes.append(f"dropped malformed document entry {d!r}")
    return out


def _assemble(raw: dict, drafted: dict) -> dict:
    """Fill in the fields the LLM doesn't own: id, level, state, source, verification."""
    name = raw.get("Scheme Name", "").strip()
    region = (raw.get("State / UT / Ministry") or "").strip()
    level = LEVEL_MAP.get(raw.get("Level"), "central")
    notes = []
    eligibility = drafted.get("eligibility") or {"all": [], "any": [], "none": [], "other": []}
    eligibility["other"] = _normalize_other(eligibility.get("other"))
    for block in ("all", "any", "none"):
        eligibility[block] = _normalize_conditions(eligibility.get(block))
    doc = {
        "schema_version": 1,
        "id": _slugify(raw.get("Scheme Slug") or name),
        "status": "active",
        "level": level,
        **({"state": STATE_CODES.get(region.lower())} if level == "state" else {}),
        "name": drafted.get("name") or {"en": name},
        "category": drafted.get("category") or [],
        "benefit": drafted.get("benefit") or {"summary": {"en": name}},
        "eligibility": eligibility,
        "documents": _normalize_documents(drafted.get("documents"), notes),
        "application": drafted.get("application") or {"mode": "offline"},
        "source": {
            "url": raw.get("Official Link") or raw.get("MyScheme URL") or "https://www.myscheme.gov.in/",
            "origin": "myscheme.gov.in",
            "external_id": raw.get("Scheme Slug"),
        },
        "verification": {"status": "draft", "notes": " ".join(
            filter(None, [drafted.get("confidence_notes"), *notes])) or None},
        "mutually_exclusive_with": [],
    }
    if drafted.get("contact"):
        doc["contact"] = drafted["contact"]
    if drafted.get("priority_groups"):
        doc["priority_groups"] = drafted["priority_groups"]
    if not doc["application"].get("url") and doc["source"]["url"].startswith("http"):
        doc["application"]["url"] = doc["source"]["url"]
    return doc


RATE_LIMIT_RETRY_S = 20.0  # offline batch tool: it's fine to just wait this out rather than give up


async def _extract_with_retry(raw: dict, attempts: int = 3) -> dict:
    for attempt in range(1, attempts + 1):
        try:
            return await extract_one(raw)
        except llm.LLMError as e:
            is_last = attempt == attempts
            if is_last or ("429" not in str(e) and "rate_limit" not in str(e)):
                raise
            wait = llm._rate_limit_wait(str(e)) or RATE_LIMIT_RETRY_S
            log.warning("rate-limited on every model; waiting %.0fs (attempt %d/%d)", wait, attempt, attempts)
            await asyncio.sleep(wait)
    raise AssertionError("unreachable")


async def run(records: list[dict]) -> tuple[list[dict], dict[str, list[str]]]:
    drafts: list[dict] = []
    failed: dict[str, list[str]] = {}
    for i, raw in enumerate(records, 1):
        name = raw.get("Scheme Name", f"#{i}")
        log.info("[%d/%d] extracting: %s", i, len(records), name)
        try:
            drafted = await _extract_with_retry(raw)
            doc = _assemble(raw, drafted)
        except llm.LLMError as e:
            failed[name] = [f"LLM error: {e}"]
            continue
        except Exception as e:  # malformed LLM output shape, etc. -- keep going, report it
            failed[name] = [f"{type(e).__name__}: {e}"]
            continue
        finally:
            await asyncio.sleep(1.5)  # spread requests out instead of bursting into the rate limit
        valid, errors = schema.check([doc])
        if valid:
            drafts.append(schema.to_document(valid[0]))
        else:
            failed[name] = errors.get(doc["id"], ["validation failed"])
    return drafts, failed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw_json", help="Path to the raw export (a JSON list of scheme records)")
    ap.add_argument("--state", help="Only records whose 'State / UT / Ministry' equals this (e.g. 'Tamil Nadu')")
    ap.add_argument("--level", choices=["central", "state"], help="Only 'central' or 'state' records")
    ap.add_argument("--limit", type=int, default=5, help="Max records to process (LLM calls cost money; default 5)")
    ap.add_argument("--out", required=True, help="Where to write the draft schemes JSON")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not llm.available():
        sys.exit("GROQ_API_KEY is not set; this tool needs the LLM to draft eligibility rules.")

    records = json.loads(Path(args.raw_json).read_text(encoding="utf-8"))
    if args.state:
        records = [r for r in records if r.get("State / UT / Ministry") == args.state]
    if args.level:
        records = [r for r in records if LEVEL_MAP.get(r.get("Level")) == args.level]
    records = records[: args.limit]
    if not records:
        sys.exit("no records match the given filters")

    config.LLM_TIMEOUT_S = max(config.LLM_TIMEOUT_S, 30.0)  # extraction output is long; the live-chat default is too short
    drafts, failed = asyncio.run(run(records))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(drafts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\nwrote {len(drafts)} draft scheme(s) -> {out_path}", file=sys.stderr)
    if failed:
        print(f"{len(failed)} failed (not written):", file=sys.stderr)
        for name, errs in failed.items():
            print(f"  - {name}: {'; '.join(errs)}", file=sys.stderr)


if __name__ == "__main__":
    main()
