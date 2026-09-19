"""
Entry point for the Urimai Telegram bot.
Runs the bot and handles incoming messages and commands.
Run Command: `python bot/main.py` from the project root (server must be running).
"""

from __future__ import annotations

import logging

from telegram import BotCommand, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

import config
import handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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


async def post_init(app: Application) -> None:
    await app.bot.set_my_commands(COMMANDS)
    await app.bot.set_my_description(
        "Urimai (உரிமை) finds government welfare schemes you may be eligible for. "
        "Talk in Tamil, English or Hindi, by text or voice note. "
        "Indicative only; the final decision is the department's."
    )
    await app.bot.set_my_short_description("Find government schemes you may be eligible for, in your language.")
    try:
        health = await handlers.backend.health()
        log.info("server health: %s", health)
    except Exception as e:
        log.warning("server not reachable at %s (%s). Start the server first.", config.BACKEND_URL, e)


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set in .env")
    # Generous timeouts: venue / hotspot networks can take several seconds to reach api.telegram.org
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .connect_timeout(30).read_timeout(40).write_timeout(40).pool_timeout(30)
        .get_updates_connect_timeout(30).get_updates_read_timeout(40)
        .post_init(post_init)
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
    app.add_handler(MessageHandler(filters.UpdateType.MESSAGE & ~filters.COMMAND, handlers.on_other))
    app.add_error_handler(handlers.on_error)

    log.info("Urimai bot starting (long polling)…")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True, bootstrap_retries=-1)


if __name__ == "__main__":
    main()
