from app.engine.derive import derive
from app.engine.rules import F, T, U, eval_condition, evaluate_scheme, k_all, k_any, neg


def test_kleene_all():
    assert k_all([]) == T
    assert k_all([T, T]) == T
    assert k_all([T, U]) == U
    assert k_all([U, F]) == F


def test_kleene_any():
    assert k_any([]) == T
    assert k_any([F, T]) == T
    assert k_any([F, U]) == U
    assert k_any([F, F]) == F


def test_neg():
    assert (neg(T), neg(F), neg(U)) == (F, T, U)


def test_ops():
    facts = {"age": 42, "gender": "female", "has_lpg_connection": False, "occupation": "agri_labourer",
             "education_level": "degree"}
    assert eval_condition(facts, {"field": "age", "op": "between", "value": [40, 79]}) == T
    assert eval_condition(facts, {"field": "age", "op": "between", "value": [18, 40]}) == F
    assert eval_condition(facts, {"field": "age", "op": "gte", "value": 60}) == F
    assert eval_condition(facts, {"field": "missing", "op": "eq", "value": 1}) == U
    assert eval_condition(facts, {"field": "has_lpg_connection", "op": "is_false"}) == T
    assert eval_condition(facts, {"field": "occupation", "op": "in", "value": ["@UNORGANISED"]}) == T
    assert eval_condition(facts, {"field": "education_level", "op": "gte", "value": "8th"}) == T
    assert eval_condition(facts, {"field": "education_level", "op": "lte", "value": "12th"}) == F


def test_none_block_unknown_stays_unknown():
    scheme = {"id": "x", "eligibility": {"all": [], "any": [], "none": [{"field": "is_epfo_member", "op": "is_true"}]}}
    assert evaluate_scheme({}, scheme)["status"] == "need_info"
    assert evaluate_scheme({"is_epfo_member": True}, scheme)["status"] == "not_eligible"
    assert evaluate_scheme({"is_epfo_member": False}, scheme)["status"] == "likely"


def test_fail_reason_mentions_user_value():
    scheme = {"id": "apy", "eligibility": {"all": [{"field": "age", "op": "between", "value": [18, 40]}]}}
    r = evaluate_scheme({"age": 42}, scheme)
    assert r["status"] == "not_eligible"
    assert "42" in r["fail_reason"]


def test_derive_inferences_do_not_override_user():
    facts, inferred = derive({"annual_family_income": 50000, "is_income_tax_payer": True, "occupation": "farmer"})
    assert facts["is_income_tax_payer"] is True
    assert facts["is_govt_employee"] is False
    assert inferred == {"is_govt_employee"}
