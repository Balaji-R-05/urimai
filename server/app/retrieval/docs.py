"""Turn the scheme catalogue (app/catalogue/loader.py: MongoDB or the JSON seed) into retrievable chunks.

Two levels (parent / child):
  parent = one section of one scheme in one language (overview, eligibility, documents, how_to_apply),
           laid out one fact per line so the splitter has clean boundaries;
  child  = recursive split of the parent body (config.CHUNK_SIZE / CHUNK_OVERLAP), each prefixed with a
           "<scheme> (<aliases>) | <section>" header so a lone fragment still says what it is about, and a
           search for "KMUT" or "PM Kisan" matches every section of that scheme.
Children are what gets embedded and ranked; the parent text is returned as context.
"""
from __future__ import annotations

from app.catalogue.loader import load_schemes
from app.core import config
from app.retrieval.chunking import recursive_split

CHUNK_FORMAT = 2  # bump when the chunk text layout changes, so stored chunks are re-embedded
MAX_HEADER_ALIASES = 6
SECTIONS = ("overview", "eligibility", "documents", "how_to_apply")
LANGS = ("en", "ta", "hi")
_LABEL = {"overview": "Overview", "eligibility": "Eligibility", "documents": "Documents needed",
          "how_to_apply": "How to apply"}

_OPS = {"eq": "is", "ne": "is not", "in": "is one of", "not_in": "is not one of", "lt": "<", "lte": "<=",
        "gt": ">", "gte": ">=", "between": "between", "is_true": "is yes", "is_false": "is no"}


def _loc(d, lang: str):
    if isinstance(d, dict):
        return d.get(lang)
    return d if lang == "en" else None


def _cond(c: dict) -> str:
    if any(k in c for k in ("all", "any", "none")):
        return "(" + "; ".join(_block(c)) + ")"
    field = c["field"].replace("_", " ")
    val = c.get("value")
    if isinstance(val, list):
        val = " and ".join(map(str, val)) if c["op"] == "between" else ", ".join(map(str, val))
    return f"{field} {_OPS.get(c['op'], c['op'])}" + ("" if val is None else f" {val}")


def _block(e: dict) -> list[str]:
    """One line per rule group."""
    lines = [f"- {_cond(c)}" for c in e.get("all", [])]
    if e.get("any"):
        lines.append("- at least one of: " + " OR ".join(_cond(c) for c in e["any"]))
    if e.get("none"):
        lines.append("- must NOT: " + " OR ".join(_cond(c) for c in e["none"]))
    lines.extend(f"- {t['en']}" for t in e.get("other", []))
    return lines


def scheme_sections(s: dict) -> list[dict]:
    """Parent documents for one scheme."""
    out = []
    base = {"scheme_id": s["id"], "level": s.get("level") or "", "category": ",".join(s.get("category", [])),
            "aliases": s.get("aliases", [])[:MAX_HEADER_ALIASES]}
    app = s.get("application", {})
    for lang in LANGS:
        name = _loc(s["name"], lang)
        if not name:
            continue
        body: dict[str, str] = {}
        benefit = _loc(s.get("benefit", {}).get("summary"), lang)
        if benefit:
            body["overview"] = f"{benefit}.\nCategories: {base['category'].replace(',', ', ').replace('_', ' ')}."
        if lang == "en":  # rules and document ids are English-only in the catalogue
            rules = _block(s.get("eligibility", {}))
            if rules:
                body["eligibility"] = "\n".join(rules)
            if s.get("documents"):
                body["documents"] = "\n".join(f"- {d.replace('_', ' ')}" for d in s["documents"])
        where = _loc(app.get("where"), lang)
        steps = _loc(app.get("steps"), lang) or []
        if where or steps:
            head = f"Mode: {app.get('mode', '')}. Where: {where}." if where else f"Mode: {app.get('mode', '')}."
            body["how_to_apply"] = "\n".join([head] + [f"{i}. {st}" for i, st in enumerate(steps, 1)])
        for section, text in body.items():
            out.append({**base, "id": f"{s['id']}#{section}#{lang}", "section": section, "lang": lang,
                        "name": name, "text": text})
    return out


def split_section(p: dict) -> list[dict]:
    aka = f" ({', '.join(p['aliases'])})" if p.get("aliases") else ""
    header = f"{p['name']}{aka} | {_LABEL[p['section']]}\n"
    pieces = recursive_split(p["text"], config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    return [{k: p[k] for k in ("scheme_id", "level", "category", "section", "lang")}
            | {"id": f"{p['id']}#{i}", "parent_id": p["id"], "text": (header + piece)[:2000]}
            for i, piece in enumerate(pieces)]


def all_sections() -> list[dict]:
    return [p for s in load_schemes() for p in scheme_sections(s)]


def all_chunks() -> list[dict]:
    return [c for p in all_sections() for c in split_section(p)]
