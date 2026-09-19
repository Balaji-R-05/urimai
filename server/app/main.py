"""Urimai API server for the Telegram bot. Run from urimai/server:  uvicorn app.main:app --port 8000"""
from __future__ import annotations

import logging

# Before the app imports below: the scheme catalogue is loaded (and logged) while they are imported
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

import asyncio  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402

from app.api.routes import router  # noqa: E402
from app.retrieval import service as retrieval  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    asyncio.get_running_loop().run_in_executor(None, retrieval.warmup)  # load models without blocking startup
    yield


app = FastAPI(title="Urimai API", version="0.1.0", lifespan=lifespan)
app.include_router(router)
