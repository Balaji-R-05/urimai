"""Extractor agent: user message (ta/en/hi/code-mixed) -> profile field updates with evidence,
plus detection of questions ABOUT schemes (answered separately from the scheme records only)."""
from __future__ import annotations

import json

from app.agents import llm
from app.catalogue.loader import load_schemes
from app.domain.fields import FIELDS

SCHEME_IDS = {s["id"] for s in load_schemes()}


def _scheme_index() -> str:
    # English names only: Tamil script costs several times more tokens (Groq free tier = 8k tokens/min/model)
    def line(s):
        aka = f" (aka {', '.join(s['aliases'][:4])})" if s.get("aliases") else ""
        return f"{s['id']}: {s['name']['en']}{aka} [{','.join(s['category'])}]"
    return "\n".join(line(s) for s in load_schemes())


def _field_catalogue() -> str:
    lines = []
    for name, meta in FIELDS.items():
        t = meta["type"]
        if t == "enum":
            desc = "one of: " + ", ".join(meta["options"])
        elif t == "children":
            desc = 'list of {"age": int, "gender": "female"|"male", "in_school": bool, "school_type": "govt"|"private"} (the FULL list of the user\'s children)'
        elif name == "annual_family_income":
            desc = 'object {"amount": number, "period": "month"|"year"} — whole family income'
        elif name == "state":
            desc = 'Indian state; use "TN" for Tamil Nadu'
        elif name == "district":
            desc = 'district name only, in standard English spelling (e.g. "Villupuram", "Coimbatore") — never Tamil script, never extra words like "near"'
        elif name == "name":
            desc = "the user's first name, in the script they used"
        else:
            desc = t
        lines.append(f"- {name}: {desc}  // {meta['label']['en']}")
    return "\n".join(lines)


SYSTEM = f"""You extract facts about an Indian citizen from their chat message, for a government welfare scheme finder.
The message may be in Tamil, Hindi, English, or mixed (e.g. Tanglish). Colloquial speech is normal.

Allowed fields:
{_field_catalogue()}

Rules:
- Output ONLY facts the user explicitly states or that are directly implied. Never guess.
  Examples of direct implication: "my husband passed away" -> marital_status=widowed (and gender=female);
  "I work in someone else's field for daily wages" -> occupation=agri_labourer; "I live in a hut" -> has_pucca_house=false;
  "PHH or AAY ration card" or "BPL card" -> has_bpl_ration_card=true; "NPHH card" -> has_bpl_ration_card=false;
  a district of Tamil Nadu -> also state=TN; "I am a government teacher" -> occupation=salaried_govt.
- If the assistant just asked a yes/no question about a field and the user answers yes/no ("ஆமா", "இல்லை", "haan", "nahi"), set that field.
  If it asked about disability and the user says they have none -> has_disability=false.
- If the user corrects an earlier fact, output the new value.
- Enum values and booleans must be exactly as listed (English). Numbers as numbers (digits).
- Money words are already converted to digits for you. "மாசம்/महीना/per month" = period month;
  "வருஷம்/साल/per year" = period year. "5k" = 5000.
- For each update include "quote": the exact words from the user's message that justify it, and "confidence" 0..1.
- Ignore anything that is not about the user or their household. Never record ID numbers (Aadhaar, phone, bank).
- If there is nothing new, return "updates": [].

Scheme questions:
The user may also ASK something about government schemes, e.g. "what documents do I need for KMUT?",
"what is PM-SYM?", "விதவை ஓய்வூதியம் எவ்வளவு கிடைக்கும்?", "is there any housing scheme?", "why am I not eligible for Atal Pension?".
If so, set "question" to {{"scheme_ids": [1-3 ids from the catalogue below that the question is about], "topic": one of
"documents" | "benefit" | "eligibility" | "how_to_apply" | "general"}}. For a general question ("any housing scheme?")
pick the most relevant ids by category. Stating facts about oneself is NOT a question; answering the assistant's
question is NOT a question. Otherwise "question": null. A message can contain both updates and a question.

Scheme catalogue (id: English name [categories]); match Tamil/Hindi scheme names to these:
{_scheme_index()}

Return JSON only: {{"updates": [{{"field": "...", "value": ..., "quote": "...", "confidence": 0.9}}], "question": null}}"""


async def extract(message: str, history: list[dict], last_field: str | None, profile: dict) -> tuple[list[dict], dict | None]:
    """Returns (updates, question). question = {"scheme_ids": [...], "topic": str} or None."""
    payload = {
        "known_profile": profile,
        "assistant_last_asked_about": last_field,
        "recent_conversation": history[-4:],
        "user_message": message,
    }
    data = await llm.complete_json(SYSTEM, json.dumps(payload, ensure_ascii=False))
    updates = data.get("updates", [])
    updates = updates if isinstance(updates, list) else []
    q = data.get("question")
    question = None
    if isinstance(q, dict):
        ids = [i for i in (q.get("scheme_ids") or []) if i in SCHEME_IDS][:3]
        # no valid ids is still a question: retrieval (app/retrieval/service.py) can find the schemes
        question = {"scheme_ids": ids, "topic": str(q.get("topic") or "general")}
    return updates, question
