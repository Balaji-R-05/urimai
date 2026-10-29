import render


def _resp(**over):
    base = {
        "results": {
            "likely": [{"scheme_id": "a", "name": "Scheme A", "status": "likely"}],
            "need_info": [],
            "not_eligible": [],
        },
        "summary": {"annual_cash_value_inr": 0, "cover_highlights": []},
        "disclaimer": None,
    }
    base.update(over)
    return base


# ---------- _clip / inr ----------

def test_clip_leaves_short_strings_alone():
    assert render._clip("short") == "short"


def test_clip_truncates_and_adds_ellipsis():
    out = render._clip("a" * 50, 10)
    assert len(out) == 10
    assert out.endswith("…")


def test_inr_groups_indian_style():
    assert render.inr(100) == "₹100"
    assert render.inr(1000) == "₹1,000"
    assert render.inr(1234567) == "₹12,34,567"


# ---------- keyboards ----------

def test_language_keyboard_has_three_languages():
    kb = render.language_keyboard()
    row = kb.inline_keyboard[0]
    assert [b.callback_data for b in row] == ["l|ta", "l|en", "l|hi"]


def test_retry_keyboard_has_single_retry_button():
    kb = render.retry_keyboard("en")
    assert len(kb.inline_keyboard) == 1
    assert kb.inline_keyboard[0][0].callback_data == "r"


# ---------- card_signature ----------

def test_card_signature_reflects_counts_and_ids():
    resp = _resp(results={
        "likely": [{"scheme_id": "a"}, {"scheme_id": "b"}],
        "need_info": [{}],
        "not_eligible": [{}, {}],
    }, summary={"annual_cash_value_inr": 5000, "cover_highlights": []})
    assert render.card_signature(resp) == (("a", "b"), 1, 2, 5000)


def test_card_signature_changes_when_results_change():
    r1 = _resp()
    r2 = _resp(results={"likely": [], "need_info": [], "not_eligible": []})
    assert render.card_signature(r1) != render.card_signature(r2)


# ---------- learned_text ----------

def test_learned_text_none_when_nothing_new():
    assert render.learned_text(_resp(), "en") is None


def test_learned_text_reports_learned_fields():
    resp = _resp(learned=[{"label": "Age", "display": "42"}])
    assert render.learned_text(resp, "en") == "📋 Got it: Age: <b>42</b>"


def test_learned_text_reports_corrections():
    resp = _resp(changes=[{"label": "Income", "from_display": "1000", "display": "2000"}])
    assert render.learned_text(resp, "en") == "✏️ Updated: Income: 1000 → <b>2000</b>"


# ---------- results_card ----------

def test_results_card_shows_no_results_hint_when_empty():
    resp = _resp(results={"likely": [], "need_info": [], "not_eligible": []})
    text, kb = render.results_card(resp, "en")
    assert "No likely schemes yet" in text
    assert len(kb.inline_keyboard) == 0


def test_results_card_lists_likely_schemes_with_buttons():
    resp = _resp(results={
        "likely": [{"scheme_id": "a", "name": "Scheme A", "status": "likely"}],
        "need_info": [],
        "not_eligible": [],
    })
    text, kb = render.results_card(resp, "en")
    assert "✅" in text
    buttons = [b for row in kb.inline_keyboard for b in row]
    assert any(b.callback_data == "s|a" for b in buttons)
    # docs button appears once there's at least one likely scheme
    assert any(b.callback_data == "d" for b in buttons)


def test_results_card_falls_back_to_default_disclaimer():
    resp = _resp(disclaimer=None)
    text, _ = render.results_card(resp, "en")
    assert "Indicative only" in text


def test_results_card_uses_response_disclaimer_when_present():
    resp = _resp(disclaimer="Custom notice")
    text, _ = render.results_card(resp, "en")
    assert "Custom notice" in text


# ---------- bucket_list ----------

def test_bucket_list_shows_fail_reason_for_not_eligible():
    resp = _resp(results={
        "likely": [], "need_info": [],
        "not_eligible": [{"scheme_id": "x", "name": "Scheme X", "fail_reason": "Too old"}],
    })
    text, kb = render.bucket_list(resp, "not_eligible", "en")
    assert "Too old" in text
    assert kb.inline_keyboard[-1][0].callback_data == "c"  # back button last


def test_bucket_list_shows_missing_labels_for_need_info():
    resp = _resp(results={
        "likely": [],
        "need_info": [{"scheme_id": "y", "name": "Scheme Y", "missing_labels": ["Age", "District"]}],
        "not_eligible": [],
    })
    text, _ = render.bucket_list(resp, "need_info", "en")
    assert "Age, District" in text


# ---------- find_result ----------

def test_find_result_searches_all_buckets():
    resp = _resp(results={
        "likely": [{"scheme_id": "a"}],
        "need_info": [{"scheme_id": "b"}],
        "not_eligible": [{"scheme_id": "c"}],
    })
    assert render.find_result(resp, "b")["scheme_id"] == "b"
    assert render.find_result(resp, "c")["scheme_id"] == "c"


def test_find_result_returns_none_when_missing():
    assert render.find_result(_resp(), "nope") is None


# ---------- scheme_detail ----------

def _scheme(**over):
    base = {
        "scheme_id": "a",
        "name": "Scheme A",
        "status": "likely",
        "benefit_summary": "₹5000/year",
        "checks": [{"text": "Age 18-60", "outcome": "pass"}],
        "documents": [{"label": "Aadhaar"}],
        "apply": {"where": "CSC", "steps": ["Visit office", "Submit form"]},
    }
    base.update(over)
    return base


def test_scheme_detail_includes_benefit_and_checks():
    resp = _resp()
    text, kb = render.scheme_detail(resp, _scheme(), "en")
    assert "₹5000/year" in text
    assert "Age 18-60" in text
    assert kb.inline_keyboard[0][0].callback_data == "c"


def test_scheme_detail_shows_fail_reason_when_not_eligible():
    resp = _resp()
    r = _scheme(status="not_eligible", fail_reason="Income too high")
    text, _ = render.scheme_detail(resp, r, "en")
    assert "Income too high" in text


def test_scheme_detail_lists_conflicting_schemes_by_name():
    resp = _resp(results={
        "likely": [_scheme(scheme_id="a", name="Scheme A")],
        "need_info": [],
        "not_eligible": [],
    })
    r = _scheme(scheme_id="a", name="Scheme A", conflicts_with=["a"])
    text, _ = render.scheme_detail(resp, r, "en")
    assert "Scheme A" in text


def test_scheme_detail_includes_official_link_when_present():
    text, _ = render.scheme_detail(_resp(), _scheme(source_url="https://example.gov.in"), "en")
    assert 'href="https://example.gov.in"' in text


# ---------- documents ----------

def test_documents_empty_message_when_none():
    assert "No documents yet" in render.documents(_resp(), "en")


def test_documents_lists_with_singular_and_plural_counts():
    resp = _resp(documents=[
        {"label": "Aadhaar", "schemes": ["a"]},
        {"label": "Income Certificate", "schemes": ["a", "b"]},
    ])
    text = render.documents(resp, "en")
    assert "Aadhaar" in text and "for 1 scheme" in text
    assert "Income Certificate" in text and "for 2 schemes" in text


# ---------- hints ----------

def test_hints_none_when_absent():
    assert render.hints(_resp(), "en") is None


def test_hints_formats_bullet_list():
    text = render.hints(_resp(hints=["Tip one", "Tip two"]), "en")
    assert "Tip one" in text and "Tip two" in text


# ---------- profile ----------

def test_profile_empty_when_no_resp():
    assert "Nothing yet" in render.profile(None, "en")


def test_profile_lists_fields_and_marks_inferred():
    resp = {"profile_view": [
        {"label": "Age", "display": "42"},
        {"label": "District", "display": "Chennai", "inferred": True},
    ]}
    text = render.profile(resp, "en")
    assert "Age: <b>42</b>" in text
    assert "District: <b>Chennai</b> <i>(inferred)</i>" in text


# ---------- reply_keyboard ----------

def test_reply_keyboard_none_when_nothing_to_show():
    assert render.reply_keyboard(_resp(), qid=1) is None


def test_reply_keyboard_includes_answered_scheme_buttons():
    resp = _resp(answered_schemes=["a"])
    kb = render.reply_keyboard(resp, qid=1)
    assert kb.inline_keyboard[0][0].callback_data == "s|a"


def test_reply_keyboard_lays_out_bool_question_three_per_row():
    resp = _resp(next_question={
        "input_type": "bool",
        "options": [{"label": "Yes"}, {"label": "No"}, {"label": "Skip"}],
    })
    kb = render.reply_keyboard(resp, qid=7)
    row = kb.inline_keyboard[0]
    assert [b.callback_data for b in row] == ["a|7|0", "a|7|1", "a|7|2"]


def test_reply_keyboard_lays_out_non_bool_question_two_per_row():
    resp = _resp(next_question={
        "input_type": "choice",
        "options": [{"label": "A"}, {"label": "B"}, {"label": "C"}],
    })
    kb = render.reply_keyboard(resp, qid=1)
    assert [len(row) for row in kb.inline_keyboard] == [2, 1]
