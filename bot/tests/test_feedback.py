"""
Tests for the inline "report wrong info" flow (handlers.py kind f/g and the feedback_for
pending-reply branch of process_text): preset categories, the free-text "other" category, and
that a backend failure is swallowed so the user still gets a "thanks" reply.
"""

from unittest.mock import AsyncMock

import handlers
import pytest
import state
from api import BackendError


class FakeChat:
    def __init__(self, chat_id):
        self.id = chat_id


class FakeMessage:
    def __init__(self, chat_id):
        self.chat = FakeChat(chat_id)


class FakeQuery:
    def __init__(self, data, chat_id):
        self.data = data
        self.message = FakeMessage(chat_id)
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()


class FakeUpdate:
    def __init__(self, data, chat_id):
        self.callback_query = FakeQuery(data, chat_id)
        self.effective_chat = FakeChat(chat_id)


class FakeCtx:
    def __init__(self):
        self.bot = AsyncMock()


@pytest.fixture
def ctx():
    return FakeCtx()


@pytest.fixture(autouse=True)
def no_real_backend(monkeypatch):
    monkeypatch.setattr(handlers.backend, "feedback", AsyncMock())


@pytest.fixture
def chat_id():
    i = len(state._states) + 1000
    while i in state._states:
        i += 1
    return i


@pytest.mark.anyio
async def test_feedback_button_shows_category_keyboard(ctx, chat_id):
    update = FakeUpdate("f|pm_kisan", chat_id)
    await handlers.on_callback(update, ctx)
    update.callback_query.answer.assert_awaited_once()
    ctx.bot.send_message.assert_awaited_once()
    assert ctx.bot.send_message.await_args.args[1] == handlers.t(
        "feedback_prompt", state.get(chat_id).lang
    )
    handlers.backend.feedback.assert_not_awaited()


@pytest.mark.anyio
async def test_feedback_preset_category_reports_and_thanks(ctx, chat_id):
    update = FakeUpdate("g|pm_kisan|amount", chat_id)
    await handlers.on_callback(update, ctx)
    handlers.backend.feedback.assert_awaited_once_with(
        "pm_kisan", state.get(chat_id).lang, "Amount/benefit wrong"
    )
    assert ctx.bot.send_message.await_args.args[1] == handlers.t(
        "feedback_thanks", state.get(chat_id).lang
    )
    assert state.get(chat_id).feedback_for is None


@pytest.mark.anyio
async def test_feedback_other_category_defers_to_free_text_reply(ctx, chat_id):
    update = FakeUpdate("g|pm_kisan|other", chat_id)
    await handlers.on_callback(update, ctx)
    handlers.backend.feedback.assert_not_awaited()
    st = state.get(chat_id)
    assert st.feedback_for == "pm_kisan"
    assert ctx.bot.send_message.await_args.args[1] == handlers.t("feedback_other_prompt", st.lang)

    await handlers.process_text(ctx, chat_id, st, "the income limit looks off")
    handlers.backend.feedback.assert_awaited_once_with(
        "pm_kisan", st.lang, "the income limit looks off"
    )
    assert st.feedback_for is None
    assert ctx.bot.send_message.await_args.args[1] == handlers.t("feedback_thanks", st.lang)


@pytest.mark.anyio
async def test_feedback_backend_failure_still_thanks_user(ctx, chat_id):
    handlers.backend.feedback.side_effect = BackendError("down")
    update = FakeUpdate("g|pm_kisan|docs", chat_id)
    await handlers.on_callback(update, ctx)
    assert ctx.bot.send_message.await_args.args[1] == handlers.t(
        "feedback_thanks", state.get(chat_id).lang
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"
