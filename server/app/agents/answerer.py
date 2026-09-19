"""Scheme Q&A: answers a citizen's question about specific schemes using ONLY those schemes' catalogue
records and the engine's evaluation for this user. It cannot invent benefits, rules or documents.
Falls back to a deterministic template if the LLM fails."""
from __future__ import annotations

import json

from app.agents import llm
from app.agents.responder import LANG_NAME
from app.domain.fields import L, tr

SYSTEM = """
You answer a citizen's question about specific Indian government welfare schemes.
Use ONLY the facts in the scheme records provided (retrieved_passages, if present, are the most relevant parts of those records). Do not add amounts, rules, documents or steps that are not in the records.
If the records do not contain the answer, say so in one sentence and point to the official website.

When relevant, mention the user's own status for the scheme from "your_status":
- "likely": say it looks likely for them (never say they ARE eligible; the department decides)
- "need_info": say what details are still needed (from "still_needed")
- "not_eligible": say why, using "reason"

Reply in {language}. Plain text, no markdown, no bullet lists. At most 4 short sentences.
Scheme names may stay as given. Never ask for Aadhaar, phone or bank numbers.
"""

LABELS = {
    "docs": L("Documents", "ஆவணங்கள்", "दस्तावेज़"),
    "apply": L("Apply at", "விண்ணப்பிக்கும் இடம்", "आवेदन"),
    "status": {
        "likely": L("looks likely for you", "உங்களுக்குக் கிடைக்க வாய்ப்புள்ளது", "आपके लिए संभावित"),
        "need_info": L("need a few more details", "இன்னும் சில தகவல்கள் தேவை", "कुछ और जानकारी चाहिए"),
        "not_eligible": L("not eligible", "தகுதியில்லை", "पात्र नहीं"),
    },
}


def _record(r: dict) -> dict:
    """Compact, already-localized view of one SchemeResult for the prompt."""
    return {
        "name": r["name"],
        "benefit": r["benefit_summary"],
        "eligibility_rules": [c["text"] for c in r["checks"]],
        "documents": [d["label"] for d in r["documents"]],
        "where_to_apply": r["apply"].get("where"),
        "steps": r["apply"].get("steps", []),
        "official_website": r.get("source_url"),
        "your_status": r["status"],
        "reason": r.get("fail_reason"),
        "still_needed": r.get("missing_labels", []),
    }


def template_answer(results: list[dict], lang: str) -> str:
    parts = []
    for r in results:
        status = tr(LABELS["status"][r["status"]], lang)
        extra = f" ({r['fail_reason']})" if r["status"] == "not_eligible" and r.get("fail_reason") else ""
        docs = ", ".join(d["label"] for d in r["documents"])
        parts.append(f"{r['name']}: {r['benefit_summary']}. {status}{extra}. "
                     f"{tr(LABELS['docs'], lang)}: {docs}. {tr(LABELS['apply'], lang)}: {r['apply'].get('where', '')}.")
    return " ".join(parts)


async def answer(*, question: str, topic: str, results: list[dict], lang: str,
                 passages: list[dict] | None = None) -> str:
    payload = {"user_question": question, "topic": topic, "schemes": [_record(r) for r in results]}
    if passages:  # retrieval's best-matching sections of these same records, most relevant first
        payload["retrieved_passages"] = passages
    text = await llm.complete_text(SYSTEM.format(language=LANG_NAME.get(lang, "English")),
                                   json.dumps(payload, ensure_ascii=False))
    return text.strip().strip('"')
