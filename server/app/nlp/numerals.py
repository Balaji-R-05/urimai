"""Deterministically rewrite spoken Tamil / Hindi number words as digits before LLM extraction.

Whisper often transcribes "5000" as "ஐயாயிரம்", which LLMs misread. Money drives eligibility, so this
must not depend on the model: "மாசம் ஐயாயிரம்" -> "மாசம் 5000", "पाँच हज़ार" -> "5000".
"""
from __future__ import annotations

import re

# Tamil compound "N-thousand" words (formal + colloquial spellings)
TA_THOUSANDS = {
    "ஆயிரம்": 1000, "ஓராயிரம்": 1000,
    "இரண்டாயிரம்": 2000, "ரெண்டாயிரம்": 2000, "இரண்டு ஆயிரம்": 2000, "ரெண்டு ஆயிரம்": 2000,
    "மூவாயிரம்": 3000, "மூணாயிரம்": 3000, "மூன்றாயிரம்": 3000,
    "நாலாயிரம்": 4000, "நான்காயிரம்": 4000,
    "ஐயாயிரம்": 5000, "ஐந்தாயிரம்": 5000, "அஞ்சாயிரம்": 5000, "அஞ்சு ஆயிரம்": 5000,
    "ஆறாயிரம்": 6000, "ஏழாயிரம்": 7000, "எட்டாயிரம்": 8000, "ஒன்பதாயிரம்": 9000,
    "பத்தாயிரம்": 10000, "பதினைந்தாயிரம்": 15000, "பதினஞ்சாயிரம்": 15000,
    "இருபதாயிரம்": 20000, "இருவதாயிரம்": 20000, "இருபத்தைந்தாயிரம்": 25000,
    "முப்பதாயிரம்": 30000, "நாற்பதாயிரம்": 40000, "ஐம்பதாயிரம்": 50000,
}
TA_UNITS = {
    "ஒரு": 1, "ஒன்று": 1, "இரண்டு": 2, "ரெண்டு": 2, "மூன்று": 3, "மூணு": 3, "நான்கு": 4, "நாலு": 4,
    "ஐந்து": 5, "அஞ்சு": 5, "ஆறு": 6, "ஏழு": 7, "எட்டு": 8, "ஒன்பது": 9, "பத்து": 10,
}
HI_UNITS = {
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5, "छह": 6, "छः": 6, "सात": 7, "आठ": 8,
    "नौ": 9, "दस": 10, "बारह": 12, "पंद्रह": 15, "बीस": 20, "पच्चीस": 25, "तीस": 30, "चालीस": 40, "पचास": 50,
}
HI_SCALES = {"हज़ार": 1000, "हजार": 1000, "लाख": 100000}
TA_SCALES = {"ஆயிரம்": 1000, "லட்சம்": 100000, "லட்சத்து": 100000, "லச்சம்": 100000}


def _alt(words) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


# "<digits or unit-word> <scale>"  e.g. "2 லட்சம்", "ரெண்டு லட்சம்", "पाँच हज़ार", "3 lakh"
_SCALED = re.compile(
    rf"(?<![\w.])(\d+(?:\.\d+)?|{_alt(TA_UNITS)}|{_alt(HI_UNITS)})\s*({_alt(TA_SCALES)}|{_alt(HI_SCALES)})"
)
_TA_COMPOUND = re.compile(_alt(k for k in TA_THOUSANDS if k != "ஆயிரம்"))


def _num(tok: str) -> float:
    if tok in TA_UNITS:
        return TA_UNITS[tok]
    if tok in HI_UNITS:
        return HI_UNITS[tok]
    return float(tok)


def to_digits(text: str) -> str:
    def scaled(m: re.Match) -> str:
        scale = TA_SCALES.get(m.group(2)) or HI_SCALES[m.group(2)]
        return str(int(_num(m.group(1)) * scale))

    text = _SCALED.sub(scaled, text)
    text = _TA_COMPOUND.sub(lambda m: str(TA_THOUSANDS[m.group(0)]), text)
    return text
