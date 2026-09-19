"""Atlas scheme search without a cluster: chunk documents, change detection, and the fuse / rerank / dedupe
logic in atlas.retrieve with the two Atlas queries stubbed."""
import pytest

from app.catalogue.loader import load_schemes
from app.retrieval import atlas, chunk_store


def _scheme(sid):
    return next(s for s in load_schemes() if s["id"] == sid)


def test_chunk_documents_match_the_in_memory_chunks():
    from app.retrieval.docs import scheme_sections, split_section
    kmut = _scheme("kmut")
    docs = chunk_store.build_chunks(kmut, "h1", "model-x")
    expected = [c["id"] for p in scheme_sections(kmut) for c in split_section(p)]
    assert [d["_id"] for d in docs] == expected
    d = docs[0]
    assert d["state"] == "TN" and d["content_hash"] == "h1" and d["embed_model"] == "model-x"
    assert d["context"] and d["text"].split("\n", 1)[0].endswith("| Overview")
    assert "embedding" not in d  # added at embed time


def test_central_schemes_are_stored_as_central():
    docs = chunk_store.build_chunks(_scheme("pm_kisan"), "h", "m")
    assert {d["state"] for d in docs} == {"central"}


def test_content_hash_changes_with_content_and_model():
    doc = {"id": "x", "name": {"en": "A"}}
    h = chunk_store.content_hash(doc, "m1")
    assert h == chunk_store.content_hash(dict(doc), "m1")
    assert h != chunk_store.content_hash({**doc, "name": {"en": "B"}}, "m1")
    assert h != chunk_store.content_hash(doc, "m2")


def test_vector_index_has_the_filters_the_queries_use():
    kind, definition = chunk_store.index_definitions(384)[chunk_store.VECTOR_INDEX]
    paths = {f["path"] for f in definition["fields"] if f["type"] == "filter"}
    assert kind == "vectorSearch" and {"state", "embed_model"} <= paths
    assert definition["fields"][0]["numDimensions"] == 384


def chunk(scheme, section, lang="en", i=0):
    return {"_id": f"{scheme}#{section}#{lang}#{i}", "scheme_id": scheme, "section": section, "lang": lang,
            "parent_id": f"{scheme}#{section}#{lang}", "text": f"{scheme} {section} {lang}",
            "context": f"{scheme} {section} context {lang}"}


class FakeColl:
    def __init__(self, parents):
        self.parents = parents

    def find(self, flt, projection):
        return [{"parent_id": p, "context": self.parents[p]} for p in flt["parent_id"]["$in"] if p in self.parents]


@pytest.fixture
def stub(monkeypatch):
    seen = {}

    def install(dense, text, parents=None, scores=None):
        def vector_search(coll, query, n, state):
            seen["v"] = state
            return dense

        def text_search(coll, query, n, state):
            seen["t"] = state
            return text

        monkeypatch.setattr(atlas, "chunks_collection", lambda: FakeColl(parents or {}))
        monkeypatch.setattr(atlas, "vector_search", vector_search)
        monkeypatch.setattr(atlas, "text_search", text_search)
        monkeypatch.setattr(atlas, "rerank", lambda q, texts: [scores.get(t, 0.1) for t in texts] if scores else None)
        return seen
    return install


def test_fuses_dedupes_and_ranks_by_reranker(stub):
    a, a2, b = chunk("pmay_g", "overview"), chunk("pmay_g", "overview", i=1), chunk("kmut", "documents")
    seen = stub(dense=[a, b], text=[a2, b], scores={b["text"]: 0.9, a["text"]: 0.5, a2["text"]: 0.4})
    hits = atlas.retrieve("house", k=5, state="TN")
    assert [(h["scheme_id"], h["section"]) for h in hits] == [("kmut", "documents"), ("pmay_g", "overview")]
    assert hits[0]["dense_rank"] == 2 and hits[0]["bm25_rank"] == 2 and hits[0]["reranked"]
    assert seen == {"v": "TN", "t": "TN"}  # the user's state reaches both Atlas queries


def test_without_reranker_keeps_fused_order(stub):
    a, b = chunk("apy", "overview"), chunk("pmsby", "overview")
    stub(dense=[a, b], text=[a])
    hits = atlas.retrieve("pension", k=5)
    assert [h["scheme_id"] for h in hits] == ["apy", "pmsby"] and not hits[0]["reranked"]


def test_context_switches_to_the_query_language(stub):
    en = chunk("ignwps", "overview", "en")
    stub(dense=[en], text=[], parents={"ignwps#overview#ta": "விதவை ஓய்வூதியம் context"})
    [h] = atlas.retrieve("விதவை ஓய்வூதியம்", k=5)
    assert h["lang"] == "ta" and h["match_lang"] == "en" and h["context"] == "விதவை ஓய்வூதியம் context"


def test_aliases_are_in_every_chunk_header_and_the_extractor_index():
    from app.agents.extractor import _scheme_index
    docs = chunk_store.build_chunks(_scheme("kmut"), "h", "m")
    assert all("(KMUT, " in d["text"].split("\n", 1)[0] for d in docs)  # every section, every language
    assert "kmut: Kalaignar Magalir Urimai Thogai (aka KMUT" in _scheme_index()


def test_chunk_format_is_part_of_the_content_hash(monkeypatch):
    from app.retrieval import chunk_store as cs
    h = cs.content_hash({"id": "x"}, "m")
    monkeypatch.setattr(cs, "CHUNK_FORMAT", cs.CHUNK_FORMAT + 1)
    assert cs.content_hash({"id": "x"}, "m") != h
