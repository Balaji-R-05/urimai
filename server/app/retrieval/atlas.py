"""Scheme search in MongoDB Atlas over the scheme_chunks collection (see chunk_store.py).

  1. recall   : $vectorSearch (meaning, local embedding of the query) + $search (keywords, e.g. "PM-KISAN"),
                each top-N, restricted to central schemes plus the user's state; fused with RRF in Python
                (the cluster runs MongoDB 8.0, so $rankFusion isn't available)
  2. precision: the local cross-encoder reranks the fused pool; one hit per (scheme, section), with the whole
                section as context, in the query's language when that version exists

Returns hits in the same shape as the in-memory search (app/retrieval/search.py).
"""
from __future__ import annotations

from app.core import config
from app.retrieval.chunk_store import TEXT_INDEX, VECTOR_INDEX, chunks_collection
from app.retrieval.embed import get_embedder
from app.retrieval.rerank import rerank
from app.retrieval.search import query_lang, rrf

NO_VECTOR = {"embedding": 0}


def _states(state: str | None) -> list[str] | None:
    return ["central", state] if state else None


def vector_search(coll, query: str, n: int, state: str | None) -> list[dict]:
    emb = get_embedder()
    filt: dict = {"embed_model": emb.name}  # vectors from another model are not comparable
    if state:
        filt["state"] = {"$in": _states(state)}
    return list(coll.aggregate([
        {"$vectorSearch": {"index": VECTOR_INDEX, "path": "embedding", "queryVector": emb.embed([query])[0],
                           "numCandidates": n * 5, "limit": n, "filter": filt}},
        {"$project": NO_VECTOR},
    ]))


def text_search(coll, query: str, n: int, state: str | None) -> list[dict]:
    compound: dict = {"must": [{"text": {"query": query, "path": "text"}}]}
    if state:
        compound["filter"] = [{"in": {"path": "state", "value": _states(state)}}]
    return list(coll.aggregate([
        {"$search": {"index": TEXT_INDEX, "compound": compound}},
        {"$limit": n},
        {"$project": NO_VECTOR},
    ]))


def _rank(ranking: list[str], cid: str) -> int | None:
    return ranking.index(cid) + 1 if cid in ranking else None


def retrieve(query: str, k: int = 5, state: str | None = None, use_rerank: bool = True) -> list[dict]:
    """Top-k section hits: {scheme_id, section, lang, score, chunk, context, per-stage ranks}."""
    coll = chunks_collection()
    n = config.CANDIDATES
    dense_docs = vector_search(coll, query, n, state)
    text_docs = text_search(coll, query, n, state)
    by_id = {d["_id"]: d for d in dense_docs + text_docs}
    dense = [d["_id"] for d in dense_docs]
    bm = [d["_id"] for d in text_docs]
    fused = rrf(dense, bm)
    pool = [by_id[cid] for cid in list(fused)[:config.RERANK_POOL]]

    rr = rerank(query, [c["text"] for c in pool]) if use_rerank else None
    hits = [{"scheme_id": c["scheme_id"], "section": c["section"], "lang": c["lang"], "parent_id": c["parent_id"],
             "chunk": c["text"], "context": c["context"], "rrf": fused[c["_id"]],
             "dense_rank": _rank(dense, c["_id"]), "bm25_rank": _rank(bm, c["_id"]),
             "reranked": rr is not None, "rerank_score": rr[i] if rr is not None else None,
             "score": rr[i] if rr is not None else fused[c["_id"]]}
            for i, c in enumerate(pool)]
    hits.sort(key=lambda h: -h["score"])

    # One hit per (scheme, section): language variants and sibling chunks are the same fact
    seen, out = set(), []
    for h in hits:
        key = (h["scheme_id"], h["section"])
        if key not in seen:
            seen.add(key)
            h["match_lang"] = h["lang"]
            out.append(h)
        if len(out) == k:
            break

    # Context in the query's language when that version of the section exists (one query for all hits)
    want = query_lang(query)
    need = {f"{h['scheme_id']}#{h['section']}#{want}": h for h in out if h["lang"] != want}
    if need:
        for d in coll.find({"parent_id": {"$in": list(need)}}, {"parent_id": 1, "context": 1}):
            h = need.pop(d["parent_id"], None)
            if h:
                h["context"], h["lang"] = d["context"], want
    return out


def warmup() -> None:
    """Load the query embedder and the reranker; the chunks themselves stay in MongoDB."""
    get_embedder().embed(["warmup"])
    rerank("warmup", ["warmup"])
