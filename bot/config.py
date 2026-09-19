import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
BACKEND_TIMEOUT_S = float(os.getenv("BACKEND_TIMEOUT_S", "30"))
VOICE_REPLIES_DEFAULT = os.getenv("VOICE_REPLIES_DEFAULT", "1") == "1"
MAX_VOICE_SECONDS = int(os.getenv("MAX_VOICE_SECONDS", "60"))
DEFAULT_LANG = os.getenv("DEFAULT_LANG", "ta")
