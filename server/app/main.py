"""
Urimai API server for the Telegram bot.
Run from urimai/server:  uvicorn app.main:app --port 8000
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Before the app imports below: the scheme catalogue is loaded (and logged) while they are imported.
# Rotating files so an unattended server can't fill the disk; console output is kept too.
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(exist_ok=True)
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
_console = logging.StreamHandler()
_console.setFormatter(_fmt)
_file = RotatingFileHandler(LOG_DIR / "server.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
_file.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_console, _file])

# Scheme feedback (app/api/routes.py) also goes to its own file, so it's easy to review without wading through the rest of the server log.
_feedback_file = RotatingFileHandler(LOG_DIR / "feedback.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
_feedback_file.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
logging.getLogger("urimai.feedback").addHandler(_feedback_file)

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.retrieval import service as retrieval


@asynccontextmanager
async def lifespan(_app: FastAPI):
    asyncio.get_running_loop().run_in_executor(None, retrieval.warmup)  # load models without blocking startup
    yield


app = FastAPI(title="Urimai API", version="0.1.0", lifespan=lifespan)
app.include_router(router)
