"""Build the user-facing result payload: localized scheme results, headline, documents, hints."""
from __future__ import annotations

from app.domain.fields import DOC_LABELS, UI, tr
from app.domain.formatting import field_label


def localize_result(r: dict, scheme: dict, lang: str) -> dict:
    app = scheme["application"]
    b = scheme["benefit"]
    return {
        **r,
        "missing_labels": [field_label(f, lang) for f in r["missing_fields"]],
        "name": tr(scheme["name"], lang),
        "level": scheme.get("level"),
        "category": scheme.get("category", []),
        "benefit_summary": tr(b.get("summary"), lang),
        "annual_cash_value_inr": b.get("annual_cash_value_inr", 0) or 0,
        "cover_highlight": tr(b.get("cover_highlight"), lang) or None,
        "documents": [{"id": d, "label": tr(scheme.get("document_labels", {}).get(d) or DOC_LABELS.get(d, d), lang)}
                      for d in scheme["documents"]],
        "apply": {
            "mode": app.get("mode"),
            "where": tr(app.get("where"), lang),
            "steps": app.get("steps", {}).get(lang) or app.get("steps", {}).get("en", []),
            "url": app.get("url"),
        },
        "unverified": scheme.get("unverified", True),
        "source_url": scheme.get("source_url"),
    }


def build_results(results: list[dict], schemes_by_id: dict, lang: str) -> dict:
    buckets = {"likely": [], "need_info": [], "not_eligible": []}
    for r in results:
        buckets[r["status"]].append(localize_result(r, schemes_by_id[r["scheme_id"]], lang))
    buckets["likely"].sort(key=lambda x: -x["annual_cash_value_inr"])
    buckets["need_info"].sort(key=lambda x: (len(x["missing_fields"]), -x["annual_cash_value_inr"]))
    return buckets


def build_summary(likely: list[dict], lang: str) -> dict:
    counted: set[str] = set()
    total = 0
    for r in sorted(likely, key=lambda x: -x["annual_cash_value_inr"]):
        if set(r["conflicts_with"]) & counted:
            continue  # choose-one group: count only the highest-value option
        counted.add(r["scheme_id"])
        total += r["annual_cash_value_inr"]
    covers = list(dict.fromkeys(r["cover_highlight"] for r in likely if r.get("cover_highlight")))
    return {"likely_count": len(likely), "annual_cash_value_inr": total, "cover_highlights": covers}


def build_documents(likely: list[dict], lang: str) -> list[dict]:
    docs: dict[str, dict] = {}
    for r in likely:
        for d in r["documents"]:
            entry = docs.setdefault(d["id"], {"doc": d["id"], "label": d["label"], "schemes": []})
            entry["schemes"].append(r["scheme_id"])
    return sorted(docs.values(), key=lambda d: -len(d["schemes"]))


def build_hints(facts: dict, lang: str) -> list[str]:
    hints = []
    if facts.get("has_girl_child_in_govt_school_14_17"):
        hints.append(tr(UI["future_pudhumai"], lang))
    if facts.get("has_boy_child_in_govt_school_14_17"):
        hints.append(tr(UI["future_pudhalvan"], lang))
    return hints
