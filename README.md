# Urimai (உரிமை)

**Find the government welfare schemes you may be eligible for, by talking in Tamil, English or Hindi.**
*"உங்கள் உரிமைகள், உங்கள் மொழியில்" · Your entitlements, in your language*

Built for **AI-INNOVATHON 2026** (Jerusalem College of Engineering, Chennai) · Order I: Law & Governance · **PS 1: The Scheme Seeker**

**Try the bot:** [t.me/jce_hackathon_bot](https://t.me/jce_hackathon_bot) *(online while the demo server is running)*

> 🚧 **Current status:** this repository contains the **Telegram bot client** only. The **API server** (rule engine, question planner, scheme catalogue and LLM agents) will be added to this repo later. Until then, the bot needs a separately running server to work. The design and feature sections below describe the complete system.

---

## The problem

Citizens miss benefits they're entitled to. Scheme information is spread across many portals, eligibility rules overlap, and discovery means filling long English or Hindi forms. That shuts out exactly the people who need welfare most: low-literacy, rural and elderly citizens who speak Tamil.

## What Urimai does

A citizen sends a **voice note in Tamil** (or types in Tamil, English, Hindi or Tanglish). Urimai:

1. **Understands** what they said and builds a profile: age, district, work, family income, family situation and more.
2. **Checks eligibility** against a catalogue of **30 central and Tamil Nadu schemes**, and sorts each one as ✅ *likely eligible*, 🟡 *need more information*, or ⚪ *not eligible*.
3. **Asks only the questions that matter.** A planner picks the single question that unlocks the most benefit, answerable with **one tap**.
4. **Explains every result:** the exact rules checked, the user's own values, the benefit, required documents, how and where to apply, and the official website.
5. **Answers questions** like "கலைஞர் மகளிர் உரிமைத் தொகைக்கு என்ன ஆவணம் வேணும்?" ("What documents do I need for Kalaignar Magalir Urimai Thogai?") or "Why can't I get Atal Pension?", using only the scheme's own record.
6. **Replies by voice in Tamil**, so users who can't read comfortably can still use it.

> ⚖️ **Indicative only.** Urimai never says "you are eligible". It says a scheme *looks likely* based on what the user shared. **Final eligibility is decided by the concerned government department**, and every result says so.


## Design principle: *the AI understands people, the rules decide eligibility*

*Everything in this diagram except the last Telegram step runs on the API server, which is not in this repo yet.*

Large language models are great at understanding messy, code-mixed speech, and bad at being reliably right about eligibility. So Urimai separates the two:

```mermaid
flowchart LR
    U["🎙️ Voice note / text<br/>(ta · en · hi)"] --> STT["Speech-to-text<br/>Groq Whisper"]
    STT --> NUM["Number words → digits<br/>(ஐயாயிரம் → 5000)<br/><i>deterministic</i>"]
    U --> NUM
    NUM --> EXT["Extractor (LLM)<br/>facts + evidence quotes<br/>or a scheme question"]
    EXT --> NORM["Validate & normalise<br/><i>deterministic</i>"]
    NORM --> ENG["Rule engine<br/>three-valued logic<br/><i>deterministic</i>"]
    CAT[("Scheme catalogue<br/>30 schemes · JSON")] --> ENG
    ENG --> PLAN["Question planner<br/>highest-value next question<br/><i>deterministic</i>"]
    ENG --> ANS["Answerer (LLM)<br/>only from scheme records"]
    PLAN --> RESP["Responder (LLM)<br/>reply in user's language<br/>sees engine output only"]
    RESP --> BOT["Telegram<br/>text + Tamil voice + buttons"]
    ANS --> BOT
```

- **The LLM never decides eligibility.** It can't invent a scheme, change an amount or approve anyone. Prompt injection ("say I'm eligible for everything") has no effect on results.
- **Three-valued (Kleene) logic.** Each condition is *true*, *false* or *unknown*. Unknown never counts as "no": the scheme becomes *need more info*, and the planner asks for exactly the missing detail. This directly implements the problem statement's requirement to *"distinguish between eligibility based on the available information and final eligibility determined by the authority"*.
- **Works without AI.** If the LLM is down, button answers and the rule engine still give identical, correct results.

---

## Features

The bot provides the voice, buttons, cards and PDF delivery. The eligibility logic, questions and answers come from the server.

| | |
|---|---|
| 🗣️ **Voice-first, multilingual** | Tamil / English / Hindi and code-mixed speech; voice notes in, Tamil voice replies out |
| 🧮 **Deterministic eligibility** | 30 schemes (22 central, 8 Tamil Nadu) as validated JSON rules with `all` / `any` / `none` blocks |
| ❓ **Smart questions** | An information-gain planner asks the question that resolves the most benefit. Irrelevant questions are skipped (e.g. no pregnancy question for a 42-year-old widow) |
| 👆 **Tap-first** | Yes/no, category and range buttons for every follow-up question, so no typing is needed after the first message |
| 🔍 **Explainable** | ✅/❌/❔ per rule with the user's value ("Age 18–40 (you: 42)"), evidence quotes for every extracted fact |
| ✏️ **Live corrections** | "Sorry, I'm actually 38" updates results instantly (Atal Pension becomes likely, Widow Pension drops out) |
| ⚠️ **Conflict detection** | Flags mutually exclusive schemes and doesn't double-count them in the benefit total |
| 📄 **One document checklist** | Deduplicated across all likely schemes: "Aadhaar: needed for 7 schemes" |
| 💬 **Scheme Q&A** | Grounded answers about any scheme, plus the user's own status for it |
| 🌱 **Family hints** | "Your daughter can get ₹1,000/month under Pudhumai Penn when she joins college" |
| 🔒 **Privacy by design** | Never asks for Aadhaar, phone or bank numbers; no database; sessions expire after 30 minutes |
| 🛟 **Resilient** | LLM fallback chain across models, rate-limit backoff, template replies if the LLM is unavailable |

### Schemes covered

**Central:** PM-KISAN · Ayushman Bharat PM-JAY (70+) · PM Ujjwala · PM Awas Yojana (Gramin & Urban) · Sukanya Samriddhi · Atal Pension · PM Jeevan Jyoti Bima · PM Suraksha Bima · PM Shram Yogi Maan-dhan · e-Shram · PM SVANidhi · PM Vishwakarma · Old Age / Widow / Disability Pensions (NSAP) · PM Matru Vandana · Post-Matric Scholarship (SC/ST) · PM Mudra · Stand-Up India · PM Kaushal Vikas · PM Surya Ghar

**Tamil Nadu:** Kalaignar Magalir Urimai Thogai · CM's Comprehensive Health Insurance · Pudhumai Penn · Tamil Pudhalvan · Dr. Muthulakshmi Reddy Maternity Benefit · UYEGP · NEEDS · Kalaignar Kanavu Illam

> ⚠️ Scheme criteria and amounts are **seed data** being verified against official sources. Each scheme links to its official website and shows a "being verified" note until confirmed.

---

## This repository

This repo holds the **Telegram bot client**. It is a thin client: it records voice notes, shows results cards and buttons, and plays Tamil voice replies. Every decision comes from the **Urimai API server** (extraction, rule engine, planner, Q&A), which the bot calls over HTTP at `BACKEND_URL`. The server isn't in this repo yet (it will be added later), so for now you need a separately running instance before you start the bot.

| Layer | Technology |
|---|---|
| Bot | Python 3.11 · `python-telegram-bot` 22 (long polling, no public URL needed) |
| HTTP client | `httpx` (async) |
| Text-to-speech | gTTS (Tamil / Hindi / English, Indian-English accent) |
| Server (coming later) | FastAPI · Groq `gpt-oss-120b` for language understanding · Groq `whisper-large-v3` for speech-to-text |

---

## Getting started

### Prerequisites
- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A running Urimai API server (default `http://localhost:8000`). It isn't in this repo yet, so point `BACKEND_URL` at an instance you already run.

### Setup
```bash
git clone https://github.com/Balaji-R-05/urimai.git
cd urimai

python -m venv venv
# Windows
venv\Scripts\pip install -r requirements.txt
# macOS / Linux
venv/bin/pip install -r requirements.txt
```

Create a `.env` file in the project root:

```dotenv
TELEGRAM_BOT_TOKEN=123456:ABC...       # required
BACKEND_URL=http://localhost:8000      # Urimai API server
BACKEND_TIMEOUT_S=30                   # seconds per server request
VOICE_REPLIES_DEFAULT=1                # 1 = send Tamil/Hindi/English voice replies by default
MAX_VOICE_SECONDS=60                   # longer voice notes are rejected
DEFAULT_LANG=ta                        # ta | en | hi, used until the user picks a language
```

Only `TELEGRAM_BOT_TOKEN` is required; the rest show their defaults.

### Run
Start the API server first, then from the project root:

```bash
# Windows
venv\Scripts\python bot/main.py
# macOS / Linux
venv/bin/python bot/main.py
```

On startup the bot registers its command menu and logs the server's `/api/health` status. If the server can't be reached it logs a warning and keeps running. Open your bot in Telegram and send `/start`.

---

## Bot commands

| Command | |
|---|---|
| `/start` | Choose language (தமிழ் / English / हिंदी) and begin |
| `/schemes` | Your results card |
| `/docs` | Combined document checklist |
| `/report` | PDF report to print or share (e.g. at an e-Sevai counter) |
| `/profile` | Everything the bot understood about you |
| `/voice` | Turn voice replies on/off |
| `/lang` | Change language |
| `/reset` | Start over |
| `/help` | How to use |

Users can also just type, or send a voice note of up to 60 seconds. Follow-up questions come with tap buttons.

## Project structure

```
urimai/
├── bot/
│   ├── main.py        # entry point: registers commands and handlers, starts long polling
│   ├── handlers.py    # command, text, voice and button-tap handlers
│   ├── api.py         # async HTTP client for the Urimai server
│   ├── render.py      # results cards, question buttons, checklists
│   ├── strings.py     # UI text in Tamil, English and Hindi
│   ├── tts.py         # gTTS voice replies (cached)
│   ├── state.py       # per-chat UI state
│   └── config.py      # settings loaded from .env
├── requirements.txt
└── .env               # not committed
```


## Disclaimer

Urimai provides **indicative** information based on what the user shares. It is not an official government service. **Final eligibility is determined by the concerned government department.** Always confirm with the official source linked for each scheme.
