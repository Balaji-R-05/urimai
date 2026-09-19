"""Two-stage retrieval over the scheme chunks.

  1. recall   : dense (in-memory) + BM25, each top-N, fused with Reciprocal Rank Fusion
  2. precision: cross-encoder rerank of the fused pool; children of the same section are collapsed and
                the full parent section is returned as context
Each stage degrades on its own: no dense model -> hashing embedder, no reranker -> RRF order.

Run from server/:
    python -m app.retrieval.search "housing scheme for poor families"
    python -m app.retrieval.search "விதவை ஓய்வூதியம்" -k 5
    python -m app.retrieval.search "documents for PM-KISAN" --section documents
"""
from __future__ import annotations

import argparse
import logging
import sys
from functools import lru_cache
from pathlib import Path

from app.core import config
from app.retrieval.bm25 import BM25
from app.retrieval.docs import all_chunks, all_sections
from app.retrieval.embed import get_embedder
from app.retrieval.rerank import rerank


@lru_cache(maxsize=1)
def _corpus():
    chunks = all_chunks()
    parents = {p["id"]: p for p in all_sections()}
    return chunks, parents, BM25([c["text"] for c in chunks])


@lru_cache(maxsize=1)
def _local_vectors():
    """Chunk vectors for in-memory dense search, cached on disk per (model, corpus)."""
    import hashlib

    import numpy as np
    chunks, _, _ = _corpus()
    emb = get_embedder()
    texts = [c["text"] for c in chunks]
    key = hashlib.sha1("\x00".join([emb.name, *texts]).encode("utf-8")).hexdigest()[:16]
    path = Path(config.MODEL_CACHE) / f"vectors-{key}.npy"
    try:
        return np.load(path)
    except Exception:
        vecs = np.asarray(emb.embed(texts), dtype="float32")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, vecs)
        except OSError:
            pass
        return vecs


def query_lang(text: str) -> str:
    """Script-based guess: Tamil / Devanagari letters, else English."""
    for ch in text:
        if "஀" <= ch <= "௿":
            return "ta"
        if "ऀ" <= ch <= "ॿ":
            return "hi"
    return "en"


def _keep(c: dict, lang: str | None, section: str | None) -> bool:
    return (not lang or c["lang"] == lang) and (not section or c["section"] == section)


def dense_local(query: str, n: int, lang: str | None, section: str | None) -> list[str]:
    import numpy as np
    chunks, _, _ = _corpus()
    q = np.asarray(get_embedder().embed([query])[0], dtype="float32")
    sims = _local_vectors() @ q
    order = [i for i in np.argsort(-sims) if _keep(chunks[i], lang, section)]
    return [chunks[i]["id"] for i in order[:n]]


def sparse(query: str, n: int, lang: str | None, section: str | None) -> list[str]:
    chunks, _, bm25 = _corpus()
    scored = [(s, c["id"]) for s, c in zip(bm25.scores(query), chunks) if s > 0 and _keep(c, lang, section)]
    return [cid for _, cid in sorted(scored, reverse=True)[:n]]


def rrf(*rankings: list[str], k: int = config.RRF_K) -> dict[str, float]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return dict(sorted(fused.items(), key=lambda kv: -kv[1]))


def _rank(ranking: list[str], cid: str) -> int | None:
    return ranking.index(cid) + 1 if cid in ranking else None


def retrieve(query: str, k: int = 5, lang: str | None = None, section: str | None = None,
             use_rerank: bool = True) -> list[dict]:
    """Top-k section hits: {scheme_id, section, lang, score, chunk, context, per-stage ranks}."""
    chunks, parents, _ = _corpus()
    by_id = {c["id"]: c for c in chunks}
    n = config.CANDIDATES

    dense = dense_local(query, n, lang, section)
    bm = sparse(query, n, lang, section)
    fused = rrf(dense, bm)
    pool = [by_id[cid] for cid in list(fused)[:n] if cid in by_id]

    rr = rerank(query, [c["text"] for c in pool]) if use_rerank else None
    hits = [{"scheme_id": c["scheme_id"], "section": c["section"], "lang": c["lang"],
             "parent_id": c["parent_id"], "chunk": c["text"], "context": parents[c["parent_id"]]["text"],
             "rrf": fused[c["id"]], "dense_rank": _rank(dense, c["id"]), "bm25_rank": _rank(bm, c["id"]),
             "reranked": rr is not None, "rerank_score": rr[i] if rr is not None else None,
             "score": rr[i] if rr is not None else fused[c["id"]]}
            for i, c in enumerate(pool)]
    hits.sort(key=lambda h: -h["score"])

    # One hit per (scheme, section): language variants and sibling children are the same fact. The best
    # child wins; the context is the whole parent section, in the query's language when we have it.
    want = lang or query_lang(query)
    seen, out = set(), []
    for h in hits:
        key = (h["scheme_id"], h["section"])
        if key in seen:
            continue
        seen.add(key)
        pref = parents.get(f"{h['scheme_id']}#{h['section']}#{want}")
        h["match_lang"] = h["lang"]
        if pref:
            h["context"], h["lang"] = pref["text"], want
        out.append(h)
    return out[:k]


def top_schemes(hits: list[dict]) -> list[str]:
    """Collapse hits to unique scheme ids, best first."""
    return list(dict.fromkeys(h["scheme_id"] for h in hits))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--lang", choices=["en", "ta", "hi"])
    ap.add_argument("--section", choices=["overview", "eligibility", "documents", "how_to_apply"])
    ap.add_argument("--no-rerank", action="store_true", help="stop after RRF fusion")
    ap.add_argument("--context", action="store_true", help="print the parent section text")
    a = ap.parse_args()

    hits = retrieve(a.query, a.k, a.lang, a.section, use_rerank=not a.no_rerank)
    print(f"{'score':>6} {'dense':>5} {'bm25':>4}  {'scheme':<24} {'section':<13} lang  chunk")
    for h in hits:
        d, b = h["dense_rank"] or "-", h["bm25_rank"] or "-"
        print(f"{h['score']:6.3f} {d:>5} {b:>4}  {h['scheme_id']:<24} {h['section']:<13} {h['lang']:<4}  "
              + h["chunk"].replace("\n", " / ")[:80])
        if a.context:
            print("        " + h["context"].replace("\n", "\n        "))
    print("\nschemes:", ", ".join(top_schemes(hits)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
