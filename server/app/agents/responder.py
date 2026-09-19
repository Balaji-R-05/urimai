"""Responder agent: phrases the reply in the user's language. It only sees engine output — it cannot
invent schemes or eligibility claims. Falls back to templates if the LLM fails."""
from __future__ import annotations

import json

from app.agents import llm
from app.domain.fields import L, tr

LANG_NAME = {
    "en": "English",
    "ta": 'Tamil (Tamil script, simple spoken style). Say "look likely" as "கிடைக்க வாய்ப்புள்ளது"',
    "hi": 'Hindi (Devanagari script, simple). Say "look likely" as "मिलने की संभावना है"',
}

SYSTEM = """You are Urimai, a warm and respectful helper that tells Indian citizens which government welfare schemes they may be eligible for.
Write the reply in {language}. Use very simple words. Maximum {max_sentences} short sentences. No markdown, no bullet lists, no emojis.

Structure:
1. Briefly acknowledge ONLY the facts in facts_learned_this_turn (at most one sentence). If that list is empty, do NOT
   restate or confirm anything from user_message — the system did not record it; just continue.
   ONLY when off_topic is true (the user replied to your question with something unrelated: small talk, a remark,
   a joke), replace steps 1 and 2 with: react warmly in a few words, matching its mood ("That's nice!", "Sorry to
   hear that."), then apologise for needing one more detail (English "Sorry", Tamil "மன்னிக்கவும்", Hindi
   "माफ़ कीजिए"), then ask next_question again. Do not discuss the unrelated topic further.
   When off_topic is false, never apologise for asking.
2. If likely_count > 0, say how many schemes look likely so far and name at most 2 from top_likely (use the given names exactly).
   Express "look likely / may be eligible" naturally in the reply language — never leave English words in a Tamil or Hindi reply
   (scheme names are the only exception).
3. If next_question is given, end by asking it naturally (you may rephrase slightly, keep the meaning). Ask only that one question.
   If next_question is null, say you have enough information and they can look at the scheme list and document checklist.

Hard rules:
- Never say the user IS eligible; say schemes "look likely" / "you may be eligible". Final decision is by the government department.
- Never mention any scheme that is not in top_likely.
- Never ask for Aadhaar number, phone number, bank account number or address.
- If the user asked something off-topic, answer in one short sentence and steer back to the question."""

TEMPLATES = {
    "thanks": L("Thank you.", "நன்றி.", "धन्यवाद।"),
    "off_topic": L("Thanks for sharing! Sorry, I just need one more detail.",
                   "பகிர்ந்ததற்கு நன்றி! மன்னிக்கவும், இன்னும் ஒரு தகவல் மட்டும் தேவை.",
                   "बताने के लिए धन्यवाद! माफ़ कीजिए, बस एक और जानकारी चाहिए।"),
    "count": L("{n} schemes look likely for you so far.", "இதுவரை {n} திட்டங்கள் உங்களுக்குக் கிடைக்க வாய்ப்புள்ளது.",
               "अब तक {n} योजनाएँ आपके लिए संभावित हैं।"),
    "done": L("I have enough information now. Please look at the scheme list and the documents checklist.",
              "இப்போது போதுமான தகவல் கிடைத்துவிட்டது. திட்டப் பட்டியலையும் ஆவணப் பட்டியலையும் பாருங்கள்.",
              "अब मेरे पास पर्याप्त जानकारी है। कृपया योजनाओं की सूची और दस्तावेज़ सूची देखें।"),
}


def template_reply(lang: str, likely_count: int, question: str | None, learned_any: bool,
                   off_topic: bool = False) -> str:
    if off_topic and question:
        return f"{tr(TEMPLATES['off_topic'], lang)} {question}"
    parts = []
    if learned_any:
        parts.append(tr(TEMPLATES["thanks"], lang))
    if likely_count:
        parts.append(tr(TEMPLATES["count"], lang).format(n=likely_count))
    parts.append(question or tr(TEMPLATES["done"], lang))
    return " ".join(parts)


async def respond(*, lang: str, user_message: str | None, learned: list[str],
                  likely_count: int, top_likely: list[str], next_question: str | None, off_topic: bool = False) -> str:
    system = SYSTEM.format(language=LANG_NAME.get(lang, "English"), max_sentences=2)  # short: read on a phone, often spoken aloud
    payload = {
        "user_message": user_message,
        "facts_learned_this_turn": learned,
        "likely_count": likely_count,
        "top_likely": top_likely[:5],
        "next_question": next_question,
        "off_topic": off_topic,
    }
    text = await llm.complete_text(system, json.dumps(payload, ensure_ascii=False))
    return text.strip().strip('"')
