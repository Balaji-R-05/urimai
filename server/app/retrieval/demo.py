"""Walkthrough of Urimai's chunking + retrieval + reranking, for judges. Run from server/:

    python -m app.retrieval.demo                 # all three parts
    python -m app.retrieval.demo --part chunking # 1: how the catalogue becomes chunks
    python -m app.retrieval.demo --part pipeline # 2: one query through every stage
    python -m app.retrieval.demo --part eval     # 3: each stage scored on eval_queries.json
    python -m app.retrieval.demo --part pipeline -q "விதவை ஓய்வூதியம்"

Runs fully in memory (no LLM). First run downloads the two models (~1.3 GB) into server/.models.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import warnings
from collections import Counter
from pathlib import Path

from app.core import config
from app.retrieval.chunking import recursive_split
from app.retrieval.docs import all_chunks, all_sections, split_section
from app.retrieval.search import _corpus, dense_local, retrieve, rrf, sparse

EVAL = Path(__file__).with_name("eval_queries.json")
SHOWCASE = ["any help to build a concrete house in my village", "விதவை ஓய்வூதியம்",
            "what documents do I need for PM-KISAN"]
W = 100


def banner(title: str) -> None:
    print("\n" + "=" * W + f"\n  {title}\n" + "=" * W)


def sub(title: str) -> None:
    print(f"\n--- {title} " + "-" * max(0, W - len(title) - 5))


def indent(text: str, pad: str = "    ") -> str:
    return pad + text.replace("\n", "\n" + pad)


def _overlap(a: str, b: str) -> int:
    """Length of the longest suffix of a that is a prefix of b."""
    for n in range(min(len(a), len(b)), 0, -1):
        if a.endswith(b[:n]):
            return n
    return 0


# ---------------------------------------------------------------------------------------------- 1
def part_chunking() -> None:
    banner("1. CHUNKING: structure-aware parents, recursive children")
    print("""
  Level 1 (parent): one scheme x one section x one language.
    sections: overview | eligibility | documents | how_to_apply     languages: en, ta (hi when present)
    Each parent is written one fact per line (a rule, a document, a step), so boundaries are clean.
  Level 2 (child): the parent is split by a RECURSIVE character splitter:
    try "\\n\\n" (paragraph) -> "\\n" (line) -> ". " (sentence) -> "। " (Hindi) -> "; " -> ", " -> " " -> chars
    Pieces that fit are merged back up to CHUNK_SIZE; OVERLAP characters carry into the next chunk.
  Every child starts with a "<scheme> | <section>" header, so a fragment never loses its subject.
  Search ranks children; the answer is given the whole parent section as context.""")

    parents, chunks = all_sections(), all_chunks()
    sub(f"Corpus (CHUNK_SIZE={config.CHUNK_SIZE}, CHUNK_OVERLAP={config.CHUNK_OVERLAP})")
    lens = [len(c["text"]) for c in chunks]
    print(f"    {len({p['scheme_id'] for p in parents})} schemes -> {len(parents)} parent sections -> "
          f"{len(chunks)} child chunks   (chars min/avg/max {min(lens)}/{sum(lens)//len(lens)}/{max(lens)})")
    by = Counter((c["section"], c["lang"]) for c in chunks)
    for sec in ("overview", "eligibility", "documents", "how_to_apply"):
        print(f"    {sec:<13} " + "  ".join(f"{lang}:{by[(sec, lang)]:>3}" for lang in ("en", "ta", "hi")))

    p = next(x for x in parents if x["id"] == "pm_kisan#how_to_apply#en")
    sub(f"Parent  {p['id']}  ({len(p['text'])} chars)")
    print(indent(p["text"]))

    sub(f"Children at production size ({config.CHUNK_SIZE} chars)")
    for c in split_section(p):
        print(f"  [{c['id']}]\n" + indent(c["text"]))

    size, ov = 60, 25
    sub(f"Same parent, stress-tested at CHUNK_SIZE={size}, OVERLAP={ov}: watch the recursion and the overlap")
    pieces = recursive_split(p["text"], size, ov)
    for i, piece in enumerate(pieces):
        o = _overlap(pieces[i - 1], piece) if i else 0
        shown = (f"«{piece[:o]}»" + piece[o:]) if o else piece
        print(f"  #{i}  {len(piece):>3} chars" + (f", {o} overlap «»" if o else "") + "\n" + indent(shown))
    too_long = sum(len(line) > size for line in p["text"].split("\n"))
    print(f"\n  Lines that fit in {size} chars split at '\\n' and are merged back up to the limit; the {too_long}"
          f" longer line(s)\n  recurse to '. ' / ', ' / ' '. «» marks text repeated from the previous chunk.")

    t = max((x for x in parents if x["lang"] == "ta"), key=lambda x: len(x["text"]))
    sub(f"Tamil works the same way  (longest Tamil section {t['id']}, {len(t['text'])} chars, CHUNK_SIZE=120)")
    for i, piece in enumerate(recursive_split(t["text"], 120, 30)):
        print(f"  #{i}  {len(piece):>3} chars\n" + indent(piece))


# ---------------------------------------------------------------------------------------------- 2
_SEC = {"overview": "overview", "eligibility": "elig", "documents": "docs", "how_to_apply": "apply"}


def _label(cid_or_hit) -> str:
    if isinstance(cid_or_hit, dict):
        s, sec = cid_or_hit["scheme_id"], cid_or_hit["section"]
    else:
        s, sec, *_ = cid_or_hit.split("#")
    return f"{s}:{_SEC[sec]}"


def _dedupe(ids: list[str], n: int) -> list[str]:
    """Chunk ids -> first n distinct scheme:section labels (what a user would see)."""
    return list(dict.fromkeys(_label(i) for i in ids))[:n]


def part_pipeline(queries: list[str]) -> None:
    banner("2. RETRIEVAL: hybrid recall -> RRF fusion -> cross-encoder rerank")
    print(f"""
  Stage A  dense  : {config.EMBED_MODEL}  (multilingual bi-encoder, cosine)
  Stage B  sparse : BM25 over words + character 4-grams (catches Tamil inflections, scheme names, numbers)
  Stage C  fuse   : Reciprocal Rank Fusion, score = sum 1/({config.RRF_K} + rank), top {config.CANDIDATES} kept
  Stage D  rerank : {config.RERANK_MODEL}  (cross-encoder reads query + chunk together)
  Then children of one section (and its en/ta twins) collapse into one hit with the full section as context.""")
    n = 5
    for q in queries:
        sub(f'Query: "{q}"')
        t0 = time.perf_counter()
        d = dense_local(q, config.CANDIDATES, None, None)
        b = sparse(q, config.CANDIDATES, None, None)
        f = list(rrf(d, b))
        final = retrieve(q, k=n)
        ms = (time.perf_counter() - t0) * 1000
        cols = [("A dense", _dedupe(d, n)), ("B BM25", _dedupe(b, n)), ("C RRF", _dedupe(f, n)),
                ("D reranked", [f"{h['score']:.2f} {_label(h)}" for h in final])]
        cw = 34
        print("  " + "".join(f"{name:<{cw}}" for name, _ in cols))
        for i in range(n):
            print("  " + "".join(f"{(col[i] if i < len(col) else ''):<{cw}}"[:cw - 1].ljust(cw) for _, col in cols))
        top = final[0]
        print(f"\n  Answer context ({top['parent_id'].rsplit('#', 1)[0]}#{top['lang']}):\n" + indent(top["context"], "    | "))
        print(f"  ({ms:.0f} ms)")


# ---------------------------------------------------------------------------------------------- 3
def _scheme_rank(labels: list[str], gold: set[str]) -> int | None:
    schemes = list(dict.fromkeys(label.split(":")[0].split("#")[0] for label in labels))
    return next((i for i, s in enumerate(schemes) if s in gold), None)


def part_eval() -> None:
    items = json.loads(EVAL.read_text(encoding="utf-8"))
    banner(f"3. EVALUATION: {len(items)} queries (en / ta / hi, keyword and paraphrase), scheme-level")
    systems = {
        "A dense only": lambda q: dense_local(q, config.CANDIDATES, None, None),
        "B BM25 only": lambda q: sparse(q, config.CANDIDATES, None, None),
        "C hybrid (RRF)": lambda q: [h["parent_id"] for h in retrieve(q, 10, use_rerank=False)],
        "D hybrid + rerank": lambda q: [h["parent_id"] for h in retrieve(q, 10)],
    }
    rows, misses = [], {}
    for name, fn in systems.items():
        h1 = h3 = mrr = 0.0
        t0 = time.perf_counter()
        for it in items:
            r = _scheme_rank(fn(it["q"]), set(it["gold"]))
            h1 += r == 0
            h3 += r is not None and r < 3
            mrr += 0 if r is None else 1 / (r + 1)
            if r != 0:
                misses.setdefault(name, []).append(it["q"])
        ms = (time.perf_counter() - t0) * 1000 / len(items)
        rows.append((name, h1, h3, mrr / len(items), ms))

    n = len(items)
    print(f"\n  {'system':<20} {'hit@1':>8} {'hit@3':>8} {'MRR':>6} {'ms/query':>9}")
    for name, h1, h3, mrr, ms in rows:
        print(f"  {name:<20} {h1/n:>7.0%} {h3/n:>8.0%} {mrr:>6.2f} {ms:>9.0f}")

    sec_items = [it for it in items if it.get("section")]
    ok = sum(retrieve(it["q"], 1)[0]["section"] == it["section"] for it in sec_items)
    print(f"\n  Section intent (top hit is the right section, e.g. 'documents' for a documents question): "
          f"{ok}/{len(sec_items)}")
    for name in systems:
        if misses.get(name):
            print(f"  missed at rank 1 by {name}: " + "; ".join(misses[name][:6])
                  + (" ..." if len(misses[name]) > 6 else ""))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    warnings.filterwarnings("ignore")
    logging.basicConfig(level=logging.ERROR)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--part", choices=["chunking", "pipeline", "eval", "all"], default="all")
    ap.add_argument("-q", "--query", action="append", help="query for the pipeline part (repeatable)")
    a = ap.parse_args()

    if a.part in ("chunking", "all"):
        part_chunking()
    if a.part in ("pipeline", "eval", "all"):
        print("\n  loading models ...", flush=True)
        _corpus()
        retrieve("warmup")
    if a.part in ("pipeline", "all"):
        part_pipeline(a.query or SHOWCASE)
    if a.part in ("eval", "all"):
        part_eval()
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
