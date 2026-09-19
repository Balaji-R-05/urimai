"""Validate and normalise LLM-extracted values into the canonical profile (app/domain/fields.py)."""
from __future__ import annotations

import re

from app.domain.fields import FIELDS, STATE_CODES, TN_DISTRICTS

MIN_CONFIDENCE = 0.5

ENUM_SYNONYMS = {
    "gender": {"woman": "female", "f": "female", "girl": "female", "man": "male", "m": "male", "boy": "male"},
    "marital_status": {"widow": "widowed", "widower": "widowed", "unmarried": "single", "never_married": "single"},
    "residence": {"village": "rural", "town": "urban", "city": "urban"},
    "caste_category": {"oc": "general", "fc": "general", "bca": "bc", "bcm": "bc", "dnc": "mbc", "sca": "sc"},
    "occupation": {"agricultural_labourer": "agri_labourer", "agri_laborer": "agri_labourer", "coolie": "daily_wage_labourer",
                   "labourer": "daily_wage_labourer", "vendor": "street_vendor", "housewife": "homemaker",
                   "government_employee": "salaried_govt", "private_employee": "salaried_private", "business": "small_business"},
    "education_level": {"sslc": "10th", "hsc": "12th", "graduate": "degree", "ug": "degree", "pg": "postgrad",
                        "bachelor": "degree", "masters": "postgrad", "illiterate": "none"},
}

_MULT = {"k": 1_000, "thousand": 1_000, "l": 100_000, "lakh": 100_000, "lakhs": 100_000, "lac": 100_000,
         "cr": 10_000_000, "crore": 10_000_000}


def parse_amount(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return None
    s = v.lower().replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "").strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*([a-z]+)?", s)
    if not m:
        return None
    n = float(m.group(1))
    return n * _MULT.get(m.group(2) or "", 1)


def _bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "y", "1"):
            return True
        if s in ("false", "no", "n", "0"):
            return False
    return None


def _children(v):
    if not isinstance(v, list):
        return None
    out = []
    for c in v:
        if not isinstance(c, dict):
            continue
        child = {}
        age = parse_amount(c.get("age"))
        if age is not None and 0 <= age <= 40:
            child["age"] = int(age)
        g = ENUM_SYNONYMS["gender"].get(str(c.get("gender", "")).lower(), str(c.get("gender", "")).lower())
        if g in ("female", "male"):
            child["gender"] = g
        if _bool(c.get("in_school")) is not None:
            child["in_school"] = _bool(c.get("in_school"))
        st = str(c.get("school_type") or "").lower()
        if st in ("govt", "government", "private"):
            child["school_type"] = "govt" if st.startswith("gov") else "private"
        if child:
            out.append(child)
    return out


def normalise_value(field: str, value):
    """Return the canonical value, or None if invalid."""
    meta = FIELDS.get(field)
    if meta is None or value is None:
        return None
    t = meta["type"]

    if field == "annual_family_income":
        if isinstance(value, dict):
            amt = parse_amount(value.get("amount"))
            period = str(value.get("period", "year")).lower()
            if amt is None:
                return None
            return int(amt * 12) if period.startswith("month") else int(amt)
        amt = parse_amount(value)
        return int(amt) if amt is not None else None

    if field == "state":
        s = str(value).strip().lower()
        return STATE_CODES.get(s, str(value).strip().upper() if len(s) <= 3 else str(value).strip().title())

    if t == "int" or t == "float":
        n = parse_amount(value)
        if n is None or not (meta.get("min", float("-inf")) <= n <= meta.get("max", float("inf"))):
            return None
        return int(n) if t == "int" else n
    if t == "bool":
        return _bool(value)
    if t == "enum":
        s = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        s = ENUM_SYNONYMS.get(field, {}).get(s, s)
        return s if s in meta["options"] else None
    if t == "children":
        return _children(value)
    if t == "str":
        s = str(value).strip()
        return s.title() if field == "district" else s or None
    return None


def apply_updates(profile: dict, updates: list[dict], turn: int, evidence: dict) -> tuple[list[dict], list[dict]]:
    """Apply extracted updates in place. Returns (learned, changes)."""
    learned, changes = [], []
    for u in updates:
        if not isinstance(u, dict):
            continue
        field = u.get("field")
        try:
            conf = float(u.get("confidence", 1))
        except (TypeError, ValueError):
            conf = 1.0
        if field not in FIELDS or conf < MIN_CONFIDENCE:
            continue
        value = normalise_value(field, u.get("value"))
        if value is None:
            continue
        old = profile.get(field)
        if old == value:
            continue
        profile[field] = value
        evidence[field] = {"value": value, "quote": str(u.get("quote") or "")[:200], "turn": turn}
        entry = {"field": field, "old": old, "new": value}
        (changes if old is not None else learned).append(entry)
        learned.extend(side_effects(profile, field, value))
    return learned, changes


def side_effects(profile: dict, field: str, value) -> list[dict]:
    """Keep related fields consistent after `field` is set. Returns extra learned entries."""
    extra = []

    def put(f, v):
        if profile.get(f) is None:
            profile[f] = v
            extra.append({"field": f, "old": None, "new": v})

    if field == "district" and isinstance(value, str) and value.lower() in TN_DISTRICTS:
        put("state", "TN")
    if field == "occupation" and value == "salaried_govt":
        put("is_govt_employee", True)
    if field == "has_disability" and value is False:
        put("disability_percent", 0)
    if field == "disability_percent" and isinstance(value, (int, float)):
        put("has_disability", value > 0)
    return extra
