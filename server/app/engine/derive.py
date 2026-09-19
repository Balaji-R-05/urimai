"""Derived fields (fields.DERIVED). Pure function: profile dict -> facts dict (profile + derived)."""
from __future__ import annotations


def _any_child(children, pred) -> bool:
    return any(pred(c) for c in children)


def derive(profile: dict) -> tuple[dict, set[str]]:
    """Return (facts, inferred_fields). Explicit user values always win over inferences."""
    facts = {k: v for k, v in profile.items() if v is not None}
    inferred: set[str] = set()

    children = profile.get("children")
    if children is not None:
        facts["has_girl_child_under_10"] = _any_child(
            children, lambda c: c.get("gender") == "female" and c.get("age") is not None and c["age"] < 10)
        facts["has_girl_child_in_govt_school_14_17"] = _any_child(
            children, lambda c: c.get("gender") == "female" and c.get("age") is not None
            and 14 <= c["age"] <= 17 and c.get("school_type") == "govt")
        facts["has_boy_child_in_govt_school_14_17"] = _any_child(
            children, lambda c: c.get("gender") == "male" and c.get("age") is not None
            and 14 <= c["age"] <= 17 and c.get("school_type") == "govt")

    caste = profile.get("caste_category")
    if caste is not None:
        facts["caste_is_sc_st"] = caste in ("sc", "st")

    occ = profile.get("occupation")
    if profile.get("is_govt_employee") is None and occ is not None:
        facts["is_govt_employee"] = occ == "salaried_govt"
        inferred.add("is_govt_employee")

    income = profile.get("annual_family_income")
    if profile.get("is_income_tax_payer") is None and income is not None and income < 300_000:
        facts["is_income_tax_payer"] = False
        inferred.add("is_income_tax_payer")

    return facts, inferred
