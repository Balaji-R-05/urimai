"""Usage counters (app/core/metrics.py): the counters themselves, the MongoDB flush, and that the
orchestrator/llm/retrieval/normalise hooks actually move them."""
import pytest
from app.core import config, metrics


def test_inc_and_snapshot():
    metrics.inc("foo")
    metrics.inc("foo", 2)
    snap = metrics.snapshot()
    assert snap["foo"] == 3
    assert "uptime_s" in snap


def test_reset_clears_counters():
    metrics.inc("foo")
    metrics.reset()
    assert "foo" not in metrics.snapshot()


def test_flush_once_is_a_noop_without_mongodb(monkeypatch):
    monkeypatch.setattr(config, "MONGODB_URI", "")
    metrics._flush_once()  # must not raise, must not try to reach MongoDB


def test_flush_once_inserts_a_snapshot_doc(monkeypatch):
    from app.core import db

    monkeypatch.setattr(config, "MONGODB_URI", "mongodb://fake")
    inserted = []

    class FakeCollection:
        def insert_one(self, doc):
            inserted.append(doc)

    monkeypatch.setattr(db, "shared",
                        lambda: {config.MONGODB_DB: {config.MONGODB_METRICS_COLLECTION: FakeCollection()}})
    metrics.inc("sessions_started")
    metrics._flush_once()
    assert len(inserted) == 1
    assert inserted[0]["sessions_started"] == 1 and "ts" in inserted[0]


def test_flush_once_swallows_insert_failures(monkeypatch):
    from app.core import db
    from pymongo.errors import PyMongoError

    monkeypatch.setattr(config, "MONGODB_URI", "mongodb://fake")

    class FailingCollection:
        def insert_one(self, doc):
            raise PyMongoError("boom")

    monkeypatch.setattr(db, "shared",
                        lambda: {config.MONGODB_DB: {config.MONGODB_METRICS_COLLECTION: FailingCollection()}})
    metrics._flush_once()  # logs a warning, does not raise


@pytest.mark.anyio
async def test_chat_counts_session_start_turn_and_language(monkeypatch):
    from app.core.session import Session
    from app.services import orchestrator

    monkeypatch.setattr(orchestrator.llm, "available", lambda: False)
    s = Session(id="m1")
    await orchestrator.chat(s, "hello", "ta")
    snap = metrics.snapshot()
    assert snap["sessions_started"] == 1
    assert snap["turns_total"] == 1
    assert snap["lang_ta"] == 1


@pytest.mark.anyio
async def test_second_turn_does_not_double_count_session_start(monkeypatch):
    from app.core.session import Session
    from app.services import orchestrator

    monkeypatch.setattr(orchestrator.llm, "available", lambda: False)
    s = Session(id="m2")
    await orchestrator.chat(s, "hello", "en")
    await orchestrator.chat(s, "again", "en")
    assert metrics.snapshot()["sessions_started"] == 1
    assert metrics.snapshot()["turns_total"] == 2


@pytest.mark.anyio
async def test_session_completion_is_counted_once(monkeypatch):
    from app.core.session import Session
    from app.services import orchestrator

    monkeypatch.setattr(orchestrator, "next_field", lambda *a, **k: None)
    s = Session(id="m3")
    r1 = await orchestrator.answer(s, "age", 50, "en")
    r2 = await orchestrator.answer(s, "age", 51, "en")
    assert r1["next_question"] is None and r2["next_question"] is None
    assert metrics.snapshot()["sessions_completed"] == 1


def test_metrics_endpoint_returns_snapshot():
    from app.main import app
    from fastapi.testclient import TestClient
    metrics.inc("sessions_started")
    r = TestClient(app).get("/api/metrics")
    assert r.status_code == 200
    assert r.json()["sessions_started"] == 1


@pytest.fixture
def anyio_backend():
    return "asyncio"
