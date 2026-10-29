"""
Server response JSON -> Telegram HTML messages + inline keyboards.

callback_data (max 64 bytes):
  l|<lang>          language picker
  s|<scheme_id>     scheme detail
  b|<bucket>        bucket list (likely / need_info / not_eligible)
  c                 back to the results card
  d                 documents checklist
  a|<qid>|<idx>     answer the pending question with option idx
  r                 retry last message
  f|<scheme_id>                prompt for "what's wrong" feedback on a scheme
  g|<scheme_id>|<category>     feedback reason: amount | docs | other (other then asks for a note)
"""

from __future__ import annotations

from html import escape

from strings import t
from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Kb

MAX_LEN = 4000
STATUS_EMOJI = {
    "likely": "✅",
    "need_info": "🟡",
    "not_eligible": "⚪"
}
CHECK_EMOJI = {
    "pass": "✅",
    "fail": "❌",
    "unknown": "❔",
    "manual": "📋"
}


# Clips a string to n characters, adding an ellipsis if it was clipped.
def _clip(s: str, n: int = 38) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# Formats an integer as Indian rupees, e.g. 1234567 -> ₹12,34,567
def inr(n: int) -> str:
    s = str(int(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return "₹" + s


# Returns a keyboard with the three supported languages.
def language_keyboard() -> Kb:
    return Kb([[
        Btn("தமிழ்", callback_data="l|ta"),
        Btn("English", callback_data="l|en"),
        Btn("हिंदी", callback_data="l|hi")
    ]])


# Returns a keyboard with a single "Retry" button.
def retry_keyboard(lang: str) -> Kb:
    return Kb([[Btn(t("btn_retry", lang), callback_data="r")]])


# Returns a signature for the results card.
def card_signature(resp: dict) -> tuple:
    res = resp["results"]
    return (tuple(r["scheme_id"] for r in res["likely"]), len(res["need_info"]), len(res["not_eligible"]),
            resp["summary"]["annual_cash_value_inr"])


# Returns the "got it / updated" message for newly learned or corrected fields, or
# None if the response has neither.
def learned_text(resp: dict, lang: str) -> str | None:
    lines = []
    if resp.get("learned"):
        items = " · ".join(f"{escape(x['label'])}: <b>{escape(x['display'])}</b>" for x in resp["learned"])
        lines.append(f"{t('understood', lang)} {items}")
    for c in resp.get("changes", []):
        lines.append(f"{t('corrected', lang)} {escape(c['label'])}: {escape(c.get('from_display', ''))} → <b>{escape(c['display'])}</b>")
    return "\n".join(lines) or None


# Returns a formatted results card.
def results_card(resp: dict, lang: str) -> tuple[str, Kb]:
    res, summ = resp["results"], resp["summary"]
    n_l, n_n, n_x = len(res["likely"]), len(res["need_info"]), len(res["not_eligible"])
    lines = [f"<b>{t('card_title', lang)}</b>",
             f"✅ {t('likely', lang)}: <b>{n_l}</b>   🟡 {t('need_info', lang)}: {n_n}   ⚪ {t('not_eligible', lang)}: {n_x}"]
    value_bits = []
    if summ["annual_cash_value_inr"]:
        value_bits.append(f"{inr(summ['annual_cash_value_inr'])} {t('per_year', lang)}")
    value_bits += summ.get("cover_highlights", [])[:3]
    if value_bits:
        lines.append("💰 " + escape(" + ".join(value_bits)))
    if not n_l:
        lines.append(t("no_results", lang))
    lines.append(f"\n⚠️ <i>{escape(resp.get('disclaimer') or t('disclaimer', lang))}</i>")

    rows = []
    shown = res["likely"][:6] if n_l else res["need_info"][:4]
    for r in shown:
        rows.append([Btn(f"{STATUS_EMOJI[r['status']]} {_clip(r['name'])}", callback_data=f"s|{r['scheme_id']}")])
    nav = []
    if n_l > 6:
        nav.append(Btn(f"✅ +{n_l - 6}", callback_data="b|likely"))
    if n_n and n_l:
        nav.append(Btn(f"🟡 {n_n}", callback_data="b|need_info"))
    if n_x:
        nav.append(Btn(f"⚪ {n_x}", callback_data="b|not_eligible"))
    if nav:
        rows.append(nav)
    if n_l:
        rows.append([Btn(t("btn_docs", lang), callback_data="d")])
    return "\n".join(lines), Kb(rows)


# Returns a formatted list of schemes in a bucket (likely / need_info / not_eligible).
def bucket_list(resp: dict, bucket: str, lang: str) -> tuple[str, Kb]:
    items = resp["results"][bucket]
    lines = [f"<b>{STATUS_EMOJI[bucket]} {t(bucket, lang)} ({len(items)})</b>"]
    for r in items[:25]:
        extra = ""
        if bucket == "not_eligible" and r.get("fail_reason"):
            extra = f" — <i>{escape(r['fail_reason'])}</i>"
        elif bucket == "need_info" and r.get("missing_labels"):
            extra = f" — <i>{escape(', '.join(r['missing_labels']))}</i>"
        lines.append(f"• {escape(r['name'])}{extra}")
    rows = [[Btn(f"{STATUS_EMOJI[bucket]} {_clip(r['name'])}", callback_data=f"s|{r['scheme_id']}")] for r in items[:12]]
    rows.append([Btn(t("btn_back", lang), callback_data="c")])
    return "\n".join(lines)[:MAX_LEN], Kb(rows)


# Returns the result for a given scheme_id, or None if not found.
def find_result(resp: dict, scheme_id: str) -> dict | None:
    for bucket in ("likely", "need_info", "not_eligible"):
        for r in resp["results"][bucket]:
            if r["scheme_id"] == scheme_id:
                return r
    return None


# Returns a formatted scheme detail view.
def scheme_detail(resp: dict, r: dict, lang: str) -> tuple[str, Kb]:
    st = r["status"]
    lines = [f"{STATUS_EMOJI[st]} <b>{escape(r['name'])}</b>  <i>({t('status_' + st, lang)})</i>",
             f"💰 {escape(r['benefit_summary'])}"]
    if r.get("priority_groups"):
        lines.append(f"⭐ {t('priority_for', lang)}: {escape(', '.join(r['priority_groups']))}")
    lines += ["", f"<b>{t('why', lang)}:</b>"]
    group_shown = False
    for c in r["checks"]:
        if c.get("group") and not group_shown:
            lines.append(f"<i>{escape(c['group'])}:</i>")
            group_shown = True
        prefix = "   " if c.get("group") else ""
        yours = f" <i>({escape(c['yours'])})</i>" if c.get("yours") else ""
        lines.append(f"{prefix}{CHECK_EMOJI[c['outcome']]} {escape(c['text'])}{yours}")
    if st == "not_eligible" and r.get("fail_reason"):
        lines.append(f"\n<b>{t('reason', lang)}:</b> {escape(r['fail_reason'])}")
    if st == "need_info" and r.get("missing_labels"):
        lines.append(f"\n<b>{t('tell_me', lang)}:</b> {escape(', '.join(r['missing_labels']))}")
    if r.get("conflicts_with"):
        names = [x["name"] for x in (find_result(resp, sid) for sid in r["conflicts_with"]) if x]
        lines.append("\n" + escape(t("choose_one", lang, names=", ".join([r["name"], *names]))))
    lines.append(f"\n<b>{t('documents', lang)}:</b> " + escape(", ".join(d["label"] for d in r["documents"])))
    app = r.get("apply") or {}
    lines.append(f"\n<b>{t('how', lang)}:</b>")
    if app.get("where"):
        lines.append(f"📍 {escape(app['where'])}")
    for i, step in enumerate(app.get("steps", []), 1):
        lines.append(f"{i}. {escape(step)}")
    if app.get("deadline"):
        lines.append(f"📅 {t('deadline', lang)}: {escape(app['deadline'])}")
    if app.get("window"):
        lines.append(f"🗓️ {escape(app['window'])}")
    contact = r.get("contact") or {}
    if contact.get("phone") or contact.get("email") or contact.get("helpline_hours"):
        lines.append(f"\n<b>{t('contact', lang)}:</b>")
        if contact.get("phone"):
            lines.append(f"📞 {escape(contact['phone'])}")
        if contact.get("email"):
            lines.append(f"✉️ {escape(contact['email'])}")
        if contact.get("helpline_hours"):
            lines.append(f"🕑 {escape(contact['helpline_hours'])}")
    url = r.get("source_url") or app.get("url")
    if url:
        lines.append(f'\n🔗 <a href="{escape(url, quote=True)}">{t("official", lang)}</a>')
    if r.get("unverified"):
        lines.append(t("unverified", lang))
    lines.append(f"\n⚠️ <i>{escape(resp.get('disclaimer') or t('disclaimer', lang))}</i>")
    rows = [
        [Btn(t("btn_feedback", lang), callback_data=f"f|{r['scheme_id']}")],
        [Btn(t("btn_back", lang), callback_data="c")],
    ]
    return "\n".join(lines)[:MAX_LEN], Kb(rows)


# Returns the three one-tap feedback reasons shown after "Report wrong info": amount/benefit,
# documents/eligibility, or other (which then asks for a short typed note).
def feedback_category_keyboard(scheme_id: str, lang: str) -> Kb:
    return Kb([
        [Btn(t("feedback_amount_btn", lang), callback_data=f"g|{scheme_id}|amount")],
        [Btn(t("feedback_docs_btn", lang), callback_data=f"g|{scheme_id}|docs")],
        [Btn(t("feedback_other_btn", lang), callback_data=f"g|{scheme_id}|other")],
    ])


# Returns a formatted documents checklist.
def documents(resp: dict, lang: str) -> str:
    docs = resp.get("documents") or []
    if not docs:
        return t("no_docs", lang)
    lines = [f"<b>{t('docs_title', lang)}</b>"]
    for d in docs:
        n = len(d["schemes"])
        needed = t("needed_for_one", lang) if n == 1 else t("needed_for", lang, n=n)
        lines.append(f"☐ {escape(d['label'])} <i>({needed})</i>")
    return "\n".join(lines)


# Returns a formatted hints message.
def hints(resp: dict, lang: str) -> str | None:
    if not resp.get("hints"):
        return None
    return f"<b>{t('hints_title', lang)}</b>\n" + "\n".join(f"• {escape(h)}" for h in resp["hints"])


# Returns a formatted profile view.
def profile(resp: dict | None, lang: str) -> str:
    view = (resp or {}).get("profile_view") or []
    if not view:
        return t("profile_empty", lang)
    lines = [f"<b>{t('profile_title', lang)}</b>"]
    for p in view:
        inf = f" <i>({t('inferred', lang)})</i>" if p.get("inferred") else ""
        lines.append(f"• {escape(p['label'])}: <b>{escape(p['display'])}</b>{inf}")
    return "\n".join(lines)


# Returns the keyboard under the bot's reply: buttons for schemes just discussed
# (opens their detail view), then quick-answer options for the next question, if any.
def reply_keyboard(resp: dict, qid: int) -> Kb | None:
    rows = []
    for sid in resp.get("answered_schemes") or []:
        r = find_result(resp, sid)
        if r:
            rows.append([Btn(f"📄 {_clip(r['name'])}", callback_data=f"s|{sid}")])
    question = resp.get("next_question")
    if question and question.get("options"):
        btns = [Btn(o["label"], callback_data=f"a|{qid}|{i}") for i, o in enumerate(question["options"])]
        per_row = 3 if question["input_type"] == "bool" else 2
        rows += [btns[i:i + per_row] for i in range(0, len(btns), per_row)]
    return Kb(rows) if rows else None
