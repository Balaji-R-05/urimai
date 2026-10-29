"""
Entry point for the Urimai Telegram bot.
Runs the bot and handles incoming messages and commands.
Run Command: `python bot/main.py` from the project root (server must be running).
"""

from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegram import BotCommand, Update
from telegram.error import TelegramError
from telegram.ext import AIORateLimiter, Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

import config
import handlers
from api import BackendError
from strings import BOT_DESCRIPTION, BOT_SHORT_DESCRIPTION

# Rotating file so an unattended bot can't fill the disk; console output is kept too.
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
_console = logging.StreamHandler()
_console.setFormatter(_fmt)
_file = RotatingFileHandler(LOG_DIR / "bot.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
_file.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_console, _file])
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("urimai.bot")


COMMANDS = [
    BotCommand("start", "Start / choose language"),
    BotCommand("schemes", "My scheme list"),
    BotCommand("docs", "Documents checklist"),
    BotCommand("report", "PDF report to print or share"),
    BotCommand("profile", "What the bot knows about me"),
    BotCommand("voice", "Voice replies on/off"),
    BotCommand("lang", "Change language"),
    BotCommand("reset", "Start again"),
    BotCommand("help", "How to use"),
]


# Pushes the bot's Telegram profile description/short description for each supported
# language, but only the ones that differ from what's live (these API calls are rate-limited).
async def set_profile_text(bot) -> None:
    """
    Description and short description per language. 
    Only changed texts are sent (these calls are rate-limited).
    """
    for lang, text in BOT_DESCRIPTION.items():
        code = lang or None
        if (await bot.get_my_description(language_code=code)).description != text:
            await bot.set_my_description(text, language_code=code)
            log.info("updated bot description (%s)", lang or "default")
    for lang, text in BOT_SHORT_DESCRIPTION.items():
        code = lang or None
        if (await bot.get_my_short_description(language_code=code)).short_description != text:
            await bot.set_my_short_description(text, language_code=code)
            log.info("updated bot short description (%s)", lang or "default")


# Closes the shared backend HTTP client when the bot shuts down.
async def post_shutdown(app: Application) -> None:
    await handlers.backend.aclose()


# Runs once after the bot starts: registers the /command menu, syncs profile text,
# and pings the backend so a misconfigured/unreachable server is obvious at startup
# (non-fatal either way — the bot still starts and handlers report errors per-request).
async def post_init(app: Application) -> None:
    await app.bot.set_my_commands(COMMANDS)
    try:
        await set_profile_text(app.bot)
    except TelegramError as e:
        log.warning("could not update bot description: %s", e)
    try:
        health = await handlers.backend.health()
        log.info("server health: %s", health)
    except BackendError as e:
        log.warning("server not reachable at %s (%s). Start the server first.", config.BACKEND_URL, e)


# Builds the Application, wires up all handlers, and runs long polling until killed.
def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set in .env")
    # Generous timeouts: venue / hotspot networks can take several seconds to reach api.telegram.org
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .connect_timeout(30).read_timeout(40).write_timeout(40).pool_timeout(30)
        .get_updates_connect_timeout(30).get_updates_read_timeout(40)
        # Throttles outgoing calls to Telegram's limits and retries on 429, so a reply
        # never silently drops just because a user is messaging faster than the limit.
        .rate_limiter(AIORateLimiter())
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)
        .build()
    )

    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("lang", handlers.cmd_lang))
    app.add_handler(CommandHandler("reset", handlers.cmd_reset))
    app.add_handler(CommandHandler("help", handlers.cmd_help))
    app.add_handler(CommandHandler("voice", handlers.cmd_voice))
    app.add_handler(CommandHandler("profile", handlers.cmd_profile))
    app.add_handler(CommandHandler("schemes", handlers.cmd_schemes))
    app.add_handler(CommandHandler("docs", handlers.cmd_docs))
    app.add_handler(CommandHandler("report", handlers.cmd_report))
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    app.add_handler(MessageHandler(filters.UpdateType.MESSAGE & filters.TEXT & ~filters.COMMAND, handlers.on_text))
    app.add_handler(MessageHandler(filters.UpdateType.MESSAGE & (filters.VOICE | filters.AUDIO), handlers.on_voice))
    # Catch-all must stay last: within a group PTB dispatches to the first handler
    # whose filters match, so text/voice are claimed above before reaching on_other.
    app.add_handler(MessageHandler(filters.UpdateType.MESSAGE & ~filters.COMMAND, handlers.on_other))
    app.add_error_handler(handlers.on_error)

    log.info("Urimai bot starting (long polling)…")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True, bootstrap_retries=-1)


if __name__ == "__main__":
    main()
