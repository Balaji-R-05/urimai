"""Scheme document schema (v1): the one definition of a valid scheme, for the JSON seed and MongoDB alike.

Used by the seed command and the loader. Export it as JSON Schema (for editors, data preparers and a MongoDB
validator) with:  python -m app.catalogue.schema  -> data/scheme.schema.json
Field-by-field guide: data/SCHEMES.md
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.core import config
from app.domain.fields import DERIVED, DOC_LABELS, FIELDS, STATE_CODES

SCHEMA_VERSION = 1

STATES = tuple(sorted(set(STATE_CODES.values())))
CATEGORIES = (
    "agriculture", "banking", "business", "child_welfare", "disability", "education", "employment", "energy",
    "fisheries", "food_security", "health", "housing", "income_support", "insurance", "legal_aid", "livestock",
    "maternity", "minority_welfare", "pension", "savings", "sc_st_welfare", "senior_citizens", "skill_development",
    "sports_culture", "transport", "water_sanitation", "women",
)
OP_NAMES = ("eq", "ne", "in", "not_in", "lt", "lte", "gt", "gte", "between", "is_true", "is_false")
FieldName = Literal[tuple(sorted(set(FIELDS) | set(DERIVED)))]  # type: ignore[valid-type]
DocId = Literal[tuple(sorted(DOC_LABELS))]  # type: ignore[valid-type]
Category = Literal[CATEGORIES]  # type: ignore[valid-type]
StateCode = Literal[STATES]  # type: ignore[valid-type]
SchemeId = Field(pattern=r"^[a-z0-9][a-z0-9_]{1,63}$")

# Keys the server adds to stored documents; stripped before validation
COMPUTED_KEYS = ("_id", "filter", "updated_at", "content_hash")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a misspelt key is an error, not silently ignored


class Text(Strict):
    """User-facing text. English is required; Tamil and Hindi fall back to English when missing."""
    en: str = Field(min_length=1)
    ta: str | None = None
    hi: str | None = None


class TextList(Strict):
    en: list[str] = Field(min_length=1)
    ta: list[str] | None = None
    hi: list[str] | None = None


class Condition(Strict):
    """One machine-checkable rule on a profile field, e.g. {"field": "age", "op": "gte", "value": 60}."""
    field: FieldName
    op: Literal[OP_NAMES]  # type: ignore[valid-type]
    value: Any = None
    text: Text | None = Field(None, description="Override the auto-generated rule text shown to users")

    @model_validator(mode="after")
    def _value_matches_field(self):
        meta = FIELDS.get(self.field) or {"type": "bool"}  # every DERIVED field is a yes/no fact
        t, op, v = meta["type"], self.op, self.value
        if t == "children":
            raise ValueError("'children' can't be used in rules; use a derived field such as has_girl_child_under_10")
        if op in ("is_true", "is_false"):
            if t != "bool":
                raise ValueError(f"'{op}' only works on yes/no fields; '{self.field}' is {t}")
            if v is not None:
                raise ValueError(f"'{op}' takes no value")
            return self
        if t == "bool":
            raise ValueError(f"'{self.field}' is a yes/no field: use op 'is_true' or 'is_false'")
        if v is None:
            raise ValueError(f"op '{op}' needs a value")
        if op == "between":
            if not (isinstance(v, list) and len(v) == 2):
                raise ValueError("'between' needs [low, high]")
            for x in v:
                _check_value(self.field, t, meta, x)
            if t in ("int", "float") and v[0] > v[1]:
                raise ValueError(f"'between' low {v[0]} is greater than high {v[1]}")
        elif op in ("in", "not_in"):
            if not (isinstance(v, list) and v):
                raise ValueError(f"'{op}' needs a non-empty list")
            for x in v:
                _check_value(self.field, t, meta, x)
        else:
            if op in ("lt", "lte", "gt", "gte") and t not in ("int", "float") and self.field != "education_level":
                raise ValueError(f"'{op}' needs a number field; '{self.field}' is {t}")
            _check_value(self.field, t, meta, v)
        return self


def _check_value(field: str, t: str, meta: dict, x) -> None:
    if t in ("int", "float"):
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            raise ValueError(f"'{field}' needs a number, got {x!r}")
        lo, hi = meta.get("min"), meta.get("max")
        if (lo is not None and x < lo) or (hi is not None and x > hi):
            raise ValueError(f"'{field}' value {x} is outside {lo}..{hi}")
    elif t == "enum":
        allowed = set(meta["options"]) | ({"@UNORGANISED"} if field == "occupation" else set())
        if x not in allowed:
            raise ValueError(f"'{field}' value {x!r} is not one of: {', '.join(sorted(allowed))}")
    elif field == "state":
        if x not in STATES:
            raise ValueError(f"unknown state code {x!r}; known: {', '.join(STATES)}")
    elif not isinstance(x, str):
        raise ValueError(f"'{field}' needs text, got {x!r}")


class Eligibility(Strict):
    """all: every rule must pass. any: at least one must pass. none: none may be true.
    other: requirements the engine can't check (shown to the user as "please check")."""
    all: list[Condition] = []
    any: list[Condition] = []
    none: list[Condition] = []
    other: list[Text] = []

    @model_validator(mode="after")
    def _has_a_rule(self):
        if not (self.all or self.any or self.none):
            raise ValueError("needs at least one rule in all / any / none; "
                             "a scheme with only 'other' text would look likely for everyone")
        return self


class Benefit(Strict):
    summary: Text
    annual_cash_value_inr: int = Field(0, ge=0, description="Cash per year, for ranking; 0 if not cash")
    cover_highlight: Text | None = Field(None, description="Non-cash headline, e.g. '₹5 lakh health cover'")


class CustomDocument(Strict):
    """A document not in the standard list (fields.DOC_LABELS)."""
    id: str = Field(pattern=r"^[a-z0-9_]{2,64}$")
    label: Text


class Application(Strict):
    mode: Literal["online", "offline", "both"]
    where: Text | None = None
    url: str | None = Field(None, pattern=r"^https?://")
    steps: TextList | None = None

    @model_validator(mode="after")
    def _says_how(self):
        if not (self.where or self.url or self.steps):
            raise ValueError("needs at least one of where / url / steps")
        return self


class Source(Strict):
    url: str = Field(pattern=r"^https?://", description="Official page the scheme details come from")
    origin: str | None = Field(None, description="Where this record came from, e.g. 'manual', 'myscheme.gov.in'")
    external_id: str | None = Field(None, description="The scheme's id at the origin, for re-imports")


class Verification(Strict):
    """draft: stored but never shown to users. unverified: shown with a 'being verified' note. verified: checked."""
    status: Literal["draft", "unverified", "verified"] = "draft"
    last_verified: dt.date | None = None
    verified_by: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _verified_has_date(self):
        if self.status == "verified" and not self.last_verified:
            raise ValueError("a verified scheme needs last_verified (YYYY-MM-DD)")
        return self


class Scheme(Strict):
    schema_version: Literal[1]
    id: str = SchemeId
    status: Literal["active", "closed"] = "active"
    level: Literal["central", "state"]
    state: StateCode | None = Field(None, description="Required for state schemes, null for central")
    category: list[Category] = Field(min_length=1)
    name: Text
    aliases: list[str] = Field([], max_length=20, description=(
        "Other names people use: abbreviations (KMUT), short forms (PM Kisan), common spellings (Tamil Puthalvan), "
        "any language. Used by scheme search"))
    benefit: Benefit
    eligibility: Eligibility
    documents: list[Union[DocId, CustomDocument]] = []
    application: Application
    source: Source
    verification: Verification = Verification()
    mutually_exclusive_with: list[str] = Field([], description="Ids of schemes a person can't get together with this")

    @model_validator(mode="after")
    def _state_matches_level(self):
        if self.level == "state" and not self.state:
            raise ValueError("a state scheme needs 'state'")
        if self.level == "central" and self.state:
            raise ValueError("a central scheme must not have 'state'")
        return self

    @field_validator("documents", mode="before")
    @classmethod
    def _documents(cls, v):
        """One clear message per bad entry (the union type would otherwise report two confusing ones)."""
        if not isinstance(v, list):
            raise ValueError("documents must be a list")
        for i, x in enumerate(v):
            if isinstance(x, str):
                if x not in DOC_LABELS:
                    raise ValueError(f"[{i}] unknown document id {x!r}: use a standard id (data/SCHEMES.md) "
                                     'or a custom one: {"id": "...", "label": {"en": "..."}}')
            elif isinstance(x, dict):
                try:
                    CustomDocument.model_validate(x)
                except ValidationError as e:
                    raise ValueError(f"[{i}] custom document: " + "; ".join(_message(err) for err in e.errors()))
            else:
                raise ValueError(f"[{i}] must be a document id or an object with id and label")
        return v

    @field_validator("aliases")
    @classmethod
    def _aliases(cls, v):
        cleaned = [a.strip() for a in v]
        if any(not a or len(a) > 80 for a in cleaned):
            raise ValueError("each alias must be 1-80 characters")
        return list(dict.fromkeys(cleaned))

    @field_validator("mutually_exclusive_with")
    @classmethod
    def _not_self(cls, v, info):
        if info.data.get("id") in v:
            raise ValueError("a scheme can't exclude itself")
        return v


def _message(err: dict) -> str:
    """'eligibility.all.2.field: 'shoe_size' is not an allowed value' instead of pydantic's full option list."""
    loc = ".".join(map(str, err["loc"])) or "(scheme)"
    msg = err["msg"].removeprefix("Value error, ")
    if err["type"] == "literal_error":
        expected = err.get("ctx", {}).get("expected", "")
        msg = f"{err['input']!r} is not an allowed value"
        if expected.count("'") <= 16:  # up to 8 options: worth listing
            msg += f" (allowed: {expected})"
        else:
            msg += " (allowed values: data/SCHEMES.md)"
    return f"{loc}: {msg}"


def check(docs: list[dict]) -> tuple[list[Scheme], dict[str, list[str]]]:
    """Validate a batch. Returns (valid schemes, {scheme id or #position: [error, ...]}); never raises."""
    valid: list[Scheme] = []
    errors: dict[str, list[str]] = {}
    seen: set[str] = set()
    for i, doc in enumerate(docs):
        key = str(doc.get("id") or f"#{i}") if isinstance(doc, dict) else f"#{i}"
        if not isinstance(doc, dict):
            errors[key] = ["not a JSON object"]
            continue
        doc = {k: v for k, v in doc.items() if k not in COMPUTED_KEYS}
        try:
            s = Scheme.model_validate(doc)
        except ValidationError as e:
            errors[key] = [_message(err) for err in e.errors()]
            continue
        if s.id in seen:
            errors[key] = ["duplicate id"]
            continue
        seen.add(s.id)
        valid.append(s)
    ids = {s.id for s in valid}
    for s in list(valid):
        unknown = [o for o in s.mutually_exclusive_with if o not in ids]
        if unknown:
            errors.setdefault(s.id, []).append(f"mutually_exclusive_with: unknown or invalid scheme(s) {unknown}")
            valid.remove(s)
    return valid, errors


def to_document(s: Scheme) -> dict:
    """The stored form: what goes into MongoDB (and back out of the seed file)."""
    return s.model_dump(mode="json", exclude_none=True)


def export_json_schema() -> dict:
    schema = Scheme.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = f"Urimai scheme (schema_version {SCHEMA_VERSION})"
    return schema


if __name__ == "__main__":
    out = config.SEED_PATH.with_name("scheme.schema.json")
    out.write_text(json.dumps(export_json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)

