"""Regression tests for the MIN_POOL short-circuit (b99ddc5): the cross-encoder is skipped below
MIN_POOL candidates, falling back to RRF order the same way an unavailable model already does."""
from app.retrieval import rerank as rerank_module
from app.retrieval.rerank import MIN_POOL, rerank


class FakeModel:
    def __init__(self):
        self.calls = []

    def rerank(self, query, texts, batch_size=16):
        self.calls.append((query, list(texts)))
        return [0.0 for _ in texts]


def test_rerank_skips_model_below_min_pool(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(rerank_module, "_model", lambda: model)
    assert rerank("q", ["a"] * (MIN_POOL - 1)) is None
    assert model.calls == []


def test_rerank_uses_model_at_min_pool(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(rerank_module, "_model", lambda: model)
    texts = ["a"] * MIN_POOL
    scores = rerank("q", texts)
    assert scores is not None and len(scores) == MIN_POOL
    assert model.calls == [("q", texts)]


def test_rerank_returns_none_without_model(monkeypatch):
    monkeypatch.setattr(rerank_module, "_model", lambda: None)
    assert rerank("q", ["a"] * MIN_POOL) is None
