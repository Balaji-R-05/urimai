"""
Run the Urimai API server and the Telegram bot together, in one terminal.

venv\\Scripts\\python run.py      # Windows
venv/bin/python run.py          # macOS / Linux

Starts the server (server/, uvicorn), waits until /api/health answers, then starts the bot (bot/main.py).
Both logs stream here, prefixed [server] / [bot]. Ctrl+C stops both; if either one exits, the other is stopped.
"""

from __future__ import annotations

import importlib.util
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
PY = sys.executable
HEALTH_TIMEOUT_S = 90
COLORS = {"server": "\033[36m", "bot": "\033[35m"}
RESET = "\033[0m"


def fail(msg: str) -> None:
    print(f"[run] {msg}", file=sys.stderr)
    sys.exit(1)


def read_env() -> dict[str, str]:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.strip().startswith("#"):
            env[key.strip()] = value.split(" #")[0].strip()
    return env


def preflight() -> int:
    """
    Check .env, dependencies and the port. Returns the server port.
    """
    if not (ROOT / ".env").exists():
        fail(".env not found. Copy .env.example to .env and fill in TELEGRAM_BOT_TOKEN and GROQ_API_KEY.")
    env = read_env()
    if not env.get("TELEGRAM_BOT_TOKEN"):
        fail("TELEGRAM_BOT_TOKEN is empty in .env")
    if not env.get("GROQ_API_KEY"):
        print("[run] warning: GROQ_API_KEY is empty; only button answers will work (no free text or voice)")

    missing = [m for m in ("telegram", "gtts", "fastapi", "uvicorn", "groq", "fpdf", "fastembed")
               if importlib.util.find_spec(m) is None]
    if missing:
        fail(f"missing packages in {PY}: {', '.join(missing)}\n"
             f"      install with: \"{PY}\" -m pip install -r requirements.txt -r server/requirements.txt")

    url = urlparse(env.get("BACKEND_URL") or "http://localhost:8000")
    if url.hostname not in ("localhost", "127.0.0.1"):
        fail(f"BACKEND_URL points to {url.hostname}; this script starts a local server, so set it to "
             "http://localhost:8000 (or run the bot alone with: python bot/main.py)")
    port = url.port or 8000
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            fail(f"port {port} is already in use. Is another Urimai server running? Stop it first.")
    return port


def stream(name: str, proc: subprocess.Popen) -> None:
    color = COLORS[name] if sys.stdout.isatty() else ""
    prefix = f"{color}[{name}]{RESET if color else ''} "
    assert proc.stdout is not None  # start() always passes stdout=PIPE
    for line in proc.stdout:
        sys.stdout.write(prefix + line)
        sys.stdout.flush()


def start(name: str, args: list[str], cwd: Path) -> subprocess.Popen:
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", creationflags=flags,
                            start_new_session=os.name != "nt")
    threading.Thread(target=stream, args=(name, proc), daemon=True).start()
    return proc


def wait_healthy(server: subprocess.Popen, port: int) -> None:
    deadline = time.time() + HEALTH_TIMEOUT_S
    while time.time() < deadline:
        if server.poll() is not None:
            fail(f"server exited with code {server.returncode} before it was ready (see [server] log above)")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
                print(f"[run] server ready: {r.read().decode()}")
                return
        except OSError:
            time.sleep(1)
    fail(f"server did not answer /api/health within {HEALTH_TIMEOUT_S}s")


def stop(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def main() -> int:
    for s in (sys.stdout, sys.stderr):  # Tamil / Hindi log lines; Windows pipes default to cp1252
        reconfigure = getattr(s, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")
    port = preflight()
    server = bot = None
    try:
        print(f"[run] starting server on http://localhost:{port} ...")
        server = start("server", [PY, "-m", "uvicorn", "app.main:app", "--port", str(port)], ROOT / "server")
        wait_healthy(server, port)
        print("[run] starting Telegram bot ... (Ctrl+C to stop both)")
        bot = start("bot", [PY, str(ROOT / "bot" / "main.py")], ROOT)
        while True:
            for name, proc in (("server", server), ("bot", bot)):
                if proc.poll() is not None:
                    print(f"[run] {name} exited with code {proc.returncode}; stopping")
                    return 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[run] stopping ...")
        return 0
    finally:
        stop(bot)
        stop(server)


if __name__ == "__main__":
    sys.exit(main())
