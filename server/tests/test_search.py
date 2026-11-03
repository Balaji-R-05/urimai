"""Regression test for the rerank-pool slicing fix (b99ddc5): retrieve() must size the reranker's input
by the precision-stage width (RERANK_POOL), not the recall-stage width (CANDIDATES)."""

from app.core import config
from app.retrieval import search as search_module
from app.retrieval.search import retrieve


def _chunk(i):
    return {
        "id": f"c{i}",
        "scheme_id": f"s{i}",
        "section": "overview",
        "lang": "en",
        "parent_id": "p0",
        "text": f"chunk{i}",
    }


def test_retrieve_slices_rerank_pool_by_rerank_pool_width(monkeypatch):
    monkeypatch.setattr(config, "CANDIDATES", 10)
    monkeypatch.setattr(config, "RERANK_POOL", 4)

    chunks = [_chunk(i) for i in range(10)]
    parents = {"p0": {"id": "p0", "text": "parent text"}}
    monkeypatch.setattr(search_module, "_corpus", lambda: (chunks, parents, None))
    monkeypatch.setattr(search_module, "dense_local", lambda *a: [c["id"] for c in chunks])
    monkeypatch.setattr(search_module, "sparse", lambda *a: [c["id"] for c in reversed(chunks)])

    seen = {}

    def fake_rerank(query, texts):
        seen["texts"] = list(texts)
        return [1.0] * len(texts)

    monkeypatch.setattr(search_module, "rerank", fake_rerank)

    retrieve("query", k=10)
    assert len(seen["texts"]) == 4  # RERANK_POOL, not CANDIDATES (10)
