"""Human-readable, localized display of profile values and rule conditions."""
from __future__ import annotations

from app.domain.fields import DERIVED, FIELDS, STATE_NAMES, UI, tr


def inr(n: int | float) -> str:
    """Indian digit grouping: 250000 -> ₹2,50,000."""
    n = int(round(n))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return ("-" if n < 0 else "") + "₹" + s


def field_label(field: str, lang: str) -> str:
    meta = FIELDS.get(field)
    if meta:
        return tr(meta["label"], lang)
    return field.replace("_", " ")


def option_label(field: str, value, lang: str) -> str:
    meta = FIELDS.get(field, {})
    opts = meta.get("options") or {}
    if value in opts:
        return tr(opts[value], lang)
    return str(value)


def bool_phrase(field: str, value: bool, lang: str) -> str:
    meta = FIELDS.get(field) or DERIVED.get(field) or {}
    key = "yes" if value else "no"
    if key in meta:
        return tr(meta[key], lang)
    return f"{field_label(field, lang)}: {'yes' if value else 'no'}"


def children_display(children: list[dict], lang: str) -> str:
    if not children:
        return tr(UI["no_children"], lang)
    parts = []
    for c in children:
        g = c.get("gender")
        word = tr(UI["daughter"] if g == "female" else UI["son"] if g == "male" else UI["child"], lang)
        age = c.get("age")
        parts.append(f"{word} {age}" if age is not None else word)
    return ", ".join(parts)


def value_display(field: str, value, lang: str) -> str:
    if value is None:
        return "—"
    meta = FIELDS.get(field, {})
    t = meta.get("type")
    if field == "annual_family_income":
        return inr(value) + tr(UI["per_year"], lang)
    if field == "state":
        return tr(STATE_NAMES.get(value, value), lang)
    for c in meta.get("choices", []):  # range buttons store a representative value; show the range
        if c["value"] == value:
            return tr(c["label"], lang)
    if field == "disability_percent":
        return f"{value}%"
    if t == "bool" or field in DERIVED:
        return bool_phrase(field, bool(value), lang)
    if t == "enum":
        return option_label(field, value, lang)
    if t == "children":
        return children_display(value, lang)
    return str(value)


def _val(field: str, v, lang: str) -> str:
    if field == "annual_family_income":
        return inr(v)
    if field == "state":
        return tr(STATE_NAMES.get(v, v), lang)
    if FIELDS.get(field, {}).get("type") == "enum":
        return option_label(field, v, lang)
    return str(v)


def condition_text(cond: dict, lang: str, negate: bool = False) -> str:
    """Requirement text for a condition. negate=True for conditions in a `none` block."""
    if cond.get("text"):
        return tr(cond["text"], lang)
    field, op, v = cond["field"], cond["op"], cond.get("value")
    label = field_label(field, lang)

    if op in ("is_true", "is_false"):
        want = (op == "is_true") != negate
        return bool_phrase(field, want, lang)

    if negate:  # only simple negations needed for the catalogue
        op = {"eq": "ne", "ne": "eq", "in": "not_in", "not_in": "in"}.get(op, op)

    if op == "between":
        return f"{label} {_val(field, v[0], lang)}–{_val(field, v[1], lang)}"
    if op in ("gte", "gt", "lte", "lt"):
        sym = {"gte": "≥", "gt": ">", "lte": "≤", "lt": "<"}[op]
        return f"{label} {sym} {_val(field, v, lang)}"
    if op == "eq":
        if FIELDS.get(field, {}).get("type") == "enum":
            return option_label(field, v, lang)
        return f"{label}: {_val(field, v, lang)}"
    if op == "ne":
        return f"{label} ≠ {_val(field, v, lang)}"
    if op in ("in", "not_in"):
        vals = " / ".join(_val(field, x, lang) for x in v)
        return f"{label}: {vals}" if op == "in" else f"{label} ≠ {vals}"
    return f"{label} {op} {v}"
