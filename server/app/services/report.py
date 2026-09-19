"""PDF report of one session: what we understood, schemes by status (with reasons), documents, how to apply.

Built in memory from the same engine output the chat shows (orchestrator.report_snapshot), never stored.
Tamil / Hindi need glyph shaping, so fpdf2 runs HarfBuzz (uharfbuzz) with Noto Sans + script fallbacks.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from app.domain.fields import L, tr

FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"

T = {
    "title": L("Scheme report", "திட்ட அறிக்கை", "योजना रिपोर्ट"),
    "subtitle": L("Government welfare schemes you may be eligible for",
                  "உங்களுக்குக் கிடைக்கக்கூடிய அரசு நலத் திட்டங்கள்",
                  "सरकारी कल्याण योजनाएँ जिनके लिए आप पात्र हो सकते हैं"),
    "generated": L("Generated", "உருவாக்கப்பட்டது", "तैयार किया गया"),
    "about_you": L("What you told us", "நீங்கள் சொன்னவை", "आपने जो बताया"),
    "inferred": L("inferred", "ஊகம்", "अनुमान"),
    "summary": L("Summary", "சுருக்கம்", "सारांश"),
    "likely": L("Likely eligible", "தகுதி பெற வாய்ப்புள்ளவை", "संभावित रूप से पात्र"),
    "need_info": L("Need more information", "மேலும் தகவல் தேவை", "और जानकारी चाहिए"),
    "not_eligible": L("Not eligible", "தகுதியில்லை", "पात्र नहीं"),
    "cash": L("Estimated cash benefit", "மதிப்பிடப்பட்ட பண உதவி", "अनुमानित नकद लाभ"),
    "per_year": L("a year", "ஆண்டுக்கு", "प्रति वर्ष"),
    "cover": L("Also covers", "மேலும்", "इसके अलावा"),
    "benefit": L("Benefit", "பயன்", "लाभ"),
    "why": L("Why", "ஏன்", "क्यों"),
    "documents": L("Documents", "ஆவணங்கள்", "दस्तावेज़"),
    "how": L("How to apply", "எப்படி விண்ணப்பிப்பது", "आवेदन कैसे करें"),
    "where": L("Where", "எங்கே", "कहाँ"),
    "official": L("Official website", "அதிகாரப்பூர்வ இணையதளம்", "आधिकारिक वेबसाइट"),
    "choose_one": L("You can get only one of", "இவற்றில் ஒன்றை மட்டுமே பெற முடியும்", "इनमें से केवल एक मिल सकती है"),
    "unverified": L("Details are being verified against the official source.",
                    "விவரங்கள் அதிகாரப்பூர்வ தகவலுடன் சரிபார்க்கப்படுகின்றன.",
                    "विवरण आधिकारिक स्रोत से सत्यापित किए जा रहे हैं।"),
    "still_needed": L("Still needed", "இன்னும் தேவை", "अभी चाहिए"),
    "reason": L("Reason", "காரணம்", "कारण"),
    "checklist": L("Documents to keep ready", "தயார் செய்ய வேண்டிய ஆவணங்கள்", "तैयार रखने वाले दस्तावेज़"),
    "for_n": L("for {n} scheme(s)", "{n} திட்டங்களுக்கு", "{n} योजनाओं के लिए"),
    "coming_up": L("Coming up for your family", "உங்கள் குடும்பத்துக்கு வரவிருப்பவை", "आपके परिवार के लिए आगे"),
    "none_likely": L("No likely schemes yet. Share a few more details in the chat to find more.",
                     "இன்னும் திட்டங்கள் கண்டறியப்படவில்லை. மேலும் விவரங்களைச் சொல்லுங்கள்.",
                     "अभी कोई संभावित योजना नहीं। चैट में थोड़ी और जानकारी दें।"),
    "privacy": L("Urimai never asks for Aadhaar, phone or bank numbers. This report is not stored.",
                 "உரிமை ஆதார், தொலைபேசி, வங்கி எண்களைக் கேட்பதில்லை. இந்த அறிக்கை சேமிக்கப்படுவதில்லை.",
                 "उरिमै कभी आधार, फ़ोन या बैंक नंबर नहीं माँगता। यह रिपोर्ट सहेजी नहीं जाती।"),
    "page": L("Page", "பக்கம்", "पृष्ठ"),
}

INK, MUTED, RULE = (33, 37, 41), (100, 108, 116), (222, 226, 230)
BRAND = (15, 98, 110)
STATUS = {"likely": (26, 127, 55), "need_info": (191, 135, 0), "not_eligible": (120, 124, 128)}
TINT = {"likely": (232, 245, 236), "need_info": (255, 246, 219), "not_eligible": (241, 243, 245)}
OUTCOME = {"pass": (26, 127, 55), "fail": (200, 50, 50), "unknown": (191, 135, 0)}
WARN_BG, WARN_INK = (255, 243, 205), (102, 77, 3)


def inr(n: int) -> str:
    s = str(int(n))
    if len(s) > 3:
        head, tail, groups = s[:-3], s[-3:], []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        s = ",".join(([head] if head else []) + groups) + "," + tail
    return "₹" + s


class ReportPDF(FPDF):
    def __init__(self, lang: str, disclaimer: str):
        super().__init__(format="A4")
        self.lang, self.disclaimer = lang, disclaimer
        for fam, stem in (("sans", "NotoSans"), ("tamil", "NotoSansTamil"), ("deva", "NotoSansDevanagari")):
            self.add_font(fam, "", FONTS / f"{stem}-Regular.ttf")
            self.add_font(fam, "B", FONTS / f"{stem}-Bold.ttf")
        self.set_fallback_fonts(["tamil", "deva"], exact_match=False)
        self.set_text_shaping(True)
        self.set_margins(16, 16, 16)
        self.set_auto_page_break(True, margin=22)
        self.alias_nb_pages()

    def t(self, key: str, **kw) -> str:
        s = tr(T[key], self.lang)
        return s.format(**kw) if kw else s

    def footer(self):
        self.set_y(-16)
        self.set_draw_color(*RULE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_font("sans", "", 7.5)
        self.set_text_color(*MUTED)
        self.multi_cell(self.epw - 22, 3.6, f"{self.disclaimer}  {self.t('privacy')}", new_x="RIGHT", new_y="TOP")
        self.cell(22, 3.6, f"{self.t('page')} {self.page_no()}/{{nb}}", align="R")

    # ---------- building blocks ----------
    def font(self, size: float, bold: bool = False, color=INK):
        self.set_font("sans", "B" if bold else "", size)
        self.set_text_color(*color)

    def para(self, text: str, size: float = 10, bold: bool = False, color=INK, indent: float = 0, h: float = 5.2):
        self.font(size, bold, color)
        self.set_x(self.l_margin + indent)
        self.multi_cell(self.epw - indent, h, text, new_x="LMARGIN", new_y="NEXT")

    def heading(self, text: str, color=BRAND):
        if self.get_y() > self.h - 50:
            self.add_page()
        self.ln(3)
        self.font(13, True, color)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*color)
        self.set_line_width(0.5)
        self.line(self.l_margin, self.get_y(), self.l_margin + 28, self.get_y())
        self.set_line_width(0.2)
        self.ln(2.5)

    def dot_line(self, text: str, color, indent: float = 4, size: float = 9.5):
        """Bullet with a coloured dot (pass / fail / unknown), wrapped text."""
        y = self.get_y()
        self.set_fill_color(*color)
        self.ellipse(self.l_margin + indent, y + 1.6, 2, 2, style="F")
        self.para(text, size=size, indent=indent + 4, h=5)

    def checkbox_line(self, text: str, note: str):
        y = self.get_y()
        self.set_draw_color(*MUTED)
        self.rect(self.l_margin + 1, y + 1, 3.6, 3.6)
        self.font(10)
        self.set_x(self.l_margin + 7)
        self.multi_cell(self.epw - 7, 5.6, f"{text}   ", new_x="END", new_y="TOP")
        self.font(8.5, color=MUTED)
        self.multi_cell(0, 5.6, note, new_x="LMARGIN", new_y="NEXT")

    def boxed(self, text: str, bg, ink, size: float = 9.5):
        self.font(size, color=ink)
        self.set_fill_color(*bg)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 5.4, text, fill=True, padding=(2.5, 3.5), new_x="LMARGIN", new_y="NEXT")

    def tag(self, text: str, status: str):
        self.set_font("sans", "B", 8)
        w = self.get_string_width(text) + 5
        self.set_fill_color(*STATUS[status])
        self.set_text_color(255, 255, 255)
        self.cell(w, 5, text, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")


def _header(pdf: ReportPDF, generated: datetime):
    pdf.set_fill_color(*BRAND)
    pdf.rect(0, 0, pdf.w, 30, style="F")
    pdf.set_xy(pdf.l_margin, 7)
    pdf.set_font("sans", "B", 20)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 9, f"Urimai · உரிமை  —  {pdf.t('title')}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("sans", "", 10)
    pdf.cell(0, 6, f"{pdf.t('subtitle')}   ·   {pdf.t('generated')}: {generated:%d %b %Y, %H:%M}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(36)


def _profile(pdf: ReportPDF, view: list[dict]):
    if not view:
        return
    pdf.heading(pdf.t("about_you"))
    label_w = 62
    for i, p in enumerate(view):
        if pdf.get_y() > pdf.h - 30:
            pdf.add_page()
        y = pdf.get_y()
        if i % 2 == 0:
            pdf.set_fill_color(247, 248, 249)
            pdf.rect(pdf.l_margin, y, pdf.epw, 6.2, style="F")
        pdf.font(9.5, color=MUTED)
        pdf.set_xy(pdf.l_margin + 2, y)
        pdf.cell(label_w, 6.2, p["label"])
        pdf.font(9.5, bold=True)
        value = p["display"] + (f"  ({pdf.t('inferred')})" if p.get("inferred") else "")
        pdf.multi_cell(pdf.epw - label_w - 2, 6.2, value, new_x="LMARGIN", new_y="NEXT")


def _summary(pdf: ReportPDF, snap: dict):
    res, summ = snap["results"], snap["summary"]
    pdf.heading(pdf.t("summary"))
    col = pdf.epw / 3
    y = pdf.get_y()
    for i, status in enumerate(("likely", "need_info", "not_eligible")):
        x = pdf.l_margin + i * col
        pdf.set_fill_color(*TINT[status])
        pdf.rect(x, y, col - 3, 17, style="F")
        pdf.set_fill_color(*STATUS[status])
        pdf.rect(x, y, 1.6, 17, style="F")
        pdf.set_xy(x + 5, y + 2)
        pdf.font(17, True, STATUS[status])
        pdf.cell(col - 10, 7, str(len(res[status])), new_x="LEFT", new_y="NEXT")
        pdf.font(8.5, color=INK)
        pdf.cell(col - 10, 5, pdf.t(status))
    pdf.set_y(y + 20)
    if summ.get("annual_cash_value_inr"):
        pdf.para(f"{pdf.t('cash')}: {inr(summ['annual_cash_value_inr'])} {pdf.t('per_year')}", size=10.5, bold=True)
    if summ.get("cover_highlights"):
        pdf.para(f"{pdf.t('cover')}: " + "; ".join(summ["cover_highlights"]), size=9.5)


def _scheme(pdf: ReportPDF, r: dict, by_id: dict):
    if pdf.get_y() > pdf.h - 60:
        pdf.add_page()
    status = r["status"]
    pdf.ln(1.5)
    top = pdf.get_y()
    pdf.para(r["name"], size=12, bold=True)
    pdf.tag(pdf.t(status), status)
    pdf.ln(1)
    if r.get("benefit_summary"):
        pdf.para(f"{pdf.t('benefit')}: {r['benefit_summary']}", size=10)
    if r.get("checks"):
        pdf.para(pdf.t("why"), size=9.5, bold=True, color=MUTED)
        for c in r["checks"]:
            text = c["text"] + (f"  ({c['yours']})" if c.get("yours") else "")
            if c.get("group"):
                text = f"{c['group']}: {text}"
            pdf.dot_line(text, OUTCOME.get(c["outcome"], MUTED))
    if r.get("conflicts_with"):
        names = [by_id[s]["name"] for s in r["conflicts_with"] if s in by_id]
        pdf.boxed(f"{pdf.t('choose_one')}: " + ", ".join([r["name"], *names]), WARN_BG, WARN_INK, size=9)
    if r.get("documents"):
        pdf.para(f"{pdf.t('documents')}: " + ", ".join(d["label"] for d in r["documents"]), size=9.5)
    app = r.get("apply") or {}
    if app.get("where") or app.get("steps"):
        pdf.para(pdf.t("how"), size=9.5, bold=True, color=MUTED)
        if app.get("where"):
            pdf.para(f"{pdf.t('where')}: {app['where']}", size=9.5, indent=4)
        for i, step in enumerate(app.get("steps") or [], 1):
            pdf.para(f"{i}. {step}", size=9.5, indent=4, h=4.9)
    url = r.get("source_url") or app.get("url")
    if url:
        pdf.font(9, color=BRAND)
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 5.5, f"{pdf.t('official')}: {url}", link=url, new_x="LMARGIN", new_y="NEXT")
    if r.get("unverified"):
        pdf.para(pdf.t("unverified"), size=8, color=MUTED)
    # status bar down the left edge of the card, then a divider
    if pdf.get_y() > top:
        pdf.set_fill_color(*STATUS[status])
        pdf.rect(pdf.l_margin - 4, top + 1, 1.2, pdf.get_y() - top - 1, style="F")
    pdf.ln(2)
    pdf.set_draw_color(*RULE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(1)


def build_report(snap: dict, lang: str, generated: datetime | None = None) -> bytes:
    """snap = orchestrator.report_snapshot(): profile_view, results, summary, documents, hints, disclaimer."""
    pdf = ReportPDF(lang, snap["disclaimer"])
    pdf.set_title(f"Urimai - {tr(T['title'], 'en')}")
    pdf.set_author("Urimai")
    pdf.add_page()
    _header(pdf, generated or datetime.now())
    pdf.boxed(snap["disclaimer"], WARN_BG, WARN_INK, size=10)  # the disclaimer always renders, first

    _profile(pdf, snap.get("profile_view") or [])
    _summary(pdf, snap)

    res = snap["results"]
    by_id = {r["scheme_id"]: r for bucket in res.values() for r in bucket}
    pdf.heading(pdf.t("likely"), STATUS["likely"])
    if res["likely"]:
        for r in res["likely"]:
            _scheme(pdf, r, by_id)
    else:
        pdf.para(pdf.t("none_likely"), size=10, color=MUTED)

    if snap.get("documents"):
        pdf.heading(pdf.t("checklist"))
        for d in snap["documents"]:
            pdf.checkbox_line(d["label"], pdf.t("for_n", n=len(d["schemes"])))

    if res["need_info"]:
        pdf.heading(pdf.t("need_info"), STATUS["need_info"])
        for r in res["need_info"]:
            pdf.dot_line(r["name"], STATUS["need_info"], indent=0, size=10)
            if r.get("missing_labels"):
                pdf.para(f"{pdf.t('still_needed')}: " + ", ".join(r["missing_labels"]), size=9, color=MUTED, indent=4)

    if res["not_eligible"]:
        pdf.heading(pdf.t("not_eligible"), STATUS["not_eligible"])
        for r in res["not_eligible"]:
            reason = f"  —  {r['fail_reason']}" if r.get("fail_reason") else ""
            pdf.dot_line(r["name"] + reason, STATUS["not_eligible"], indent=0, size=9.5)

    if snap.get("hints"):
        pdf.heading(pdf.t("coming_up"))
        for h in snap["hints"]:
            pdf.dot_line(h, BRAND, indent=0)

    return bytes(pdf.output())
