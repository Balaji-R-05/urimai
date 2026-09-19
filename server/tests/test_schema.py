"""Scheme schema v1: the seed data is valid, and common data mistakes are caught with a readable message."""
import copy

import pytest

from app.catalogue.loader import CatalogueError, read_seed, validate
from app.catalogue.schema import check


def one(**changes):
    """The kmut seed record with some keys replaced (None deletes a key)."""
    s = copy.deepcopy(next(x for x in read_seed() if x["id"] == "kmut"))
    s["mutually_exclusive_with"] = []
    for k, v in changes.items():
        if v is None:
            s.pop(k, None)
        else:
            s[k] = v
    return s


def errors_for(doc) -> list[str]:
    valid, errors = check([doc])
    return next(iter(errors.values()), [])


def test_seed_file_is_valid_v1():
    valid, errors = check(read_seed())
    assert not errors and len(valid) == 30


@pytest.mark.parametrize("change, expected", [
    ({"eligibilty": {}}, "eligibilty: Extra inputs are not permitted"),
    ({"level": "district"}, "level: 'district' is not an allowed value (allowed: 'central' or 'state')"),
    ({"state": None}, "a state scheme needs 'state'"),
    ({"state": "XX"}, "state: 'XX' is not an allowed value"),
    ({"category": ["weather"]}, "category.0: 'weather' is not an allowed value"),
    ({"documents": ["pan_card"]}, "unknown document id 'pan_card'"),
    ({"name": {"ta": "பெயர்"}}, "name.en: Field required"),
    ({"schema_version": 2}, "schema_version"),
    ({"id": "KMUT Scheme"}, "id: String should match pattern"),
    ({"verification": {"status": "verified"}}, "a verified scheme needs last_verified"),
    ({"source": {"url": "kmut.tn.gov.in"}}, "source.url: String should match pattern"),
])
def test_scheme_level_mistakes(change, expected):
    assert any(expected in e for e in errors_for(one(**change))), errors_for(one(**change))


@pytest.mark.parametrize("rule, expected", [
    ({"field": "shoe_size", "op": "eq", "value": 9}, "'shoe_size' is not an allowed value"),
    ({"field": "age", "op": "gte", "value": "60"}, "'age' needs a number"),
    ({"field": "age", "op": "gte", "value": 200}, "outside 0..120"),
    ({"field": "age", "op": "between", "value": [60, 18]}, "low 60 is greater than high 18"),
    ({"field": "gender", "op": "eq", "value": "Female"}, "'Female' is not one of"),
    ({"field": "is_pregnant", "op": "eq", "value": True}, "use op 'is_true' or 'is_false'"),
    ({"field": "age", "op": "is_true"}, "only works on yes/no fields"),
    ({"field": "caste_category", "op": "in", "value": "sc"}, "needs a non-empty list"),
    ({"field": "children", "op": "eq", "value": 1}, "use a derived field"),
    ({"field": "state", "op": "eq", "value": "Tamil Nadu"}, "unknown state code"),
])
def test_rule_mistakes(rule, expected):
    elig = {"all": [rule]}
    assert any(expected in e for e in errors_for(one(eligibility=elig))), errors_for(one(eligibility=elig))


def test_other_text_alone_is_not_enough():
    errs = errors_for(one(eligibility={"other": [{"en": "Must be poor"}]}))
    assert any("needs at least one rule" in e for e in errs)


def test_unknown_exclusion_partner_is_reported():
    _, errors = check([one(mutually_exclusive_with=["no_such_scheme"])])
    assert "no_such_scheme" in errors["kmut"][0]


def test_custom_documents_and_manual_checks_reach_the_engine():
    from app.engine.rules import evaluate_scheme
    doc = one(documents=["aadhaar", {"id": "fishing_licence", "label": {"en": "Fishing licence"}}],
              eligibility={"all": [{"field": "gender", "op": "eq", "value": "female"}],
                           "other": [{"en": "Registered with the fisheries department"}]})
    [s] = validate([doc])
    assert s["documents"] == ["aadhaar", "fishing_licence"]
    assert s["document_labels"]["fishing_licence"]["en"] == "Fishing licence"
    r = evaluate_scheme({"gender": "female", "state": "TN"}, s)
    assert r["status"] == "likely"  # the manual check never changes the result
    assert {"text": "Registered with the fisheries department", "field": None, "outcome": "manual"} in r["checks"]


def test_drafts_and_closed_schemes_are_not_served():
    docs = [one(), one(id="kmut_draft", verification={"status": "draft"}), one(id="kmut_old", status="closed")]
    assert [s["id"] for s in validate(docs)] == ["kmut"]


def test_mongo_mode_skips_bad_documents_but_seed_mode_does_not():
    docs = [one(), one(id="broken", level="district")]
    assert [s["id"] for s in validate(docs, strict=False)] == ["kmut"]
    with pytest.raises(CatalogueError, match="broken"):
        validate(docs, strict=True)


def test_aliases_are_trimmed_deduplicated_and_bounded():
    [s], errors = check([one(aliases=[" KMUT ", "KMUT", "Magalir Urimai"])])
    assert not errors and s.aliases == ["KMUT", "Magalir Urimai"]
    assert any("1-80 characters" in e for e in errors_for(one(aliases=["  "])))
    assert any("aliases" in e for e in errors_for(one(aliases=[f"a{i}" for i in range(21)])))
