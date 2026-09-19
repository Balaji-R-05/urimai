"""HTTP endpoints under /api. The Telegram bot calls these through bot/api.py."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from app.agents import llm
from app.api.schemas import AnswerRequest, ChatRequest, EvaluateRequest, Lang, SessionRequest
from app.core import config, session
from app.domain.fields import FIELDS, tr
from app.retrieval import service as retrieval
from app.services import orchestrator, report

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"ok": True, "llm": "up" if llm.available() else "down", "model": config.LLM_MODEL,
            "schemes": len(orchestrator.SCHEMES), "catalogue": "mongodb" if config.MONGODB_URI else "seed"}


@router.post("/chat")
async def chat(req: ChatRequest):
    s = session.get(req.session_id)
    async with s.lock:
        return await orchestrator.chat(s, req.message.strip(), req.lang)


@router.post("/answer")
async def answer(req: AnswerRequest):
    if req.field not in FIELDS:
        raise HTTPException(400, f"unknown field '{req.field}'")
    s = session.get(req.session_id)
    async with s.lock:
        return await orchestrator.answer(s, req.field, req.value, req.lang, req.skip)


@router.post("/evaluate")
async def evaluate(req: EvaluateRequest):
    """Evaluate a complete profile in one call, without a session or the LLM (testing and debugging)."""
    return await orchestrator.evaluate_profile(req.profile, req.lang)


@router.post("/session/reset")
async def reset(req: SessionRequest):
    session.reset(req.session_id)
    return {"ok": True}


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    s = session.peek(session_id)
    if not s or not s.last_response:
        raise HTTPException(404, "no such session")
    return s.last_response


@router.get("/session/{session_id}/report")
async def session_report(session_id: str, lang: Lang = "en"):
    """PDF report of the session: profile, schemes by status with reasons, documents, how to apply.
    Built in memory and streamed back; nothing is written to disk."""
    s = session.peek(session_id)
    if not s or not s.profile:
        raise HTTPException(404, "no profile in this session yet")
    snap = orchestrator.report_snapshot(s, lang)
    pdf = await asyncio.to_thread(report.build_report, snap, lang)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="urimai-report-{lang}.pdf"'})


@router.get("/search")
async def search(q: str, k: int = 5, state: str | None = None):
    """Retrieval pipeline, every stage visible: dense rank, BM25 rank, RRF, reranker score."""
    hits = await retrieval.search(q, state)
    if hits is None:
        raise HTTPException(503, "retrieval unavailable")
    return {"query": q, "hits": [{**t, "chunk": h["chunk"], "context": h["context"]}
                                 for t, h in zip(retrieval.trace_view(hits), hits)][:k]}


@router.get("/schemes")
async def schemes(lang: Lang = "en"):
    return [{"id": s["id"], "name": tr(s["name"], lang), "level": s["level"], "state": s.get("state"),
             "category": s["category"], "unverified": s["unverified"]} for s in orchestrator.SCHEMES]


@router.get("/schemes/{scheme_id}")
async def scheme(scheme_id: str):
    s = orchestrator.SCHEMES_BY_ID.get(scheme_id)
    if not s:
        raise HTTPException(404, "unknown scheme")
    return s


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...), lang: str = Form("ta")):
    audio = await file.read()
    if not audio:
        raise HTTPException(400, "empty audio")
    if len(audio) > 20 * 1024 * 1024:
        raise HTTPException(413, "audio too large")
    try:
        text = await llm.transcribe(audio, file.filename or "voice.ogg", lang)
    except llm.LLMError as e:
        raise HTTPException(502, f"transcription failed: {e}")
    return {"text": text}
