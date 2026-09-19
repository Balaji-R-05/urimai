"""Keep the scheme_chunks collection (and its Atlas search indexes) in step with the schemes collection.

Each served scheme is split into section chunks (app/retrieval/docs.py, the same chunks the in-memory search
uses), embedded locally, and stored with its vector:

    {_id: "kmut#documents#ta#0", scheme_id, section, lang, state: "TN" | "central", level, parent_id,
     text, context, content_hash, embed_model, embedding: float32 x dims}

Only schemes whose content (or the embedder / chunk settings) changed are re-embedded; chunks of removed,
draft or closed schemes are deleted. Runs as part of the seed command, or alone:

    python -m app.retrieval.chunk_store
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
import time

from bson.binary import Binary, BinaryVectorDtype

from app.catalogue.loader import served, to_engine
from app.catalogue.schema import check, to_document
from app.core import config, db
from app.retrieval.docs import CHUNK_FORMAT, scheme_sections, split_section
from app.retrieval.embed import get_embedder

log = logging.getLogger("urimai.chunks")

VECTOR_INDEX = "chunks_vector"
TEXT_INDEX = "chunks_text"
EMBED_BATCH = 128


def chunks_collection(client=None):
    return (client or db.shared())[config.MONGODB_DB][config.MONGODB_CHUNKS_COLLECTION]


def content_hash(doc: dict, embed_model: str) -> str:
    """Changes when the scheme, the embedding model or the chunk layout / settings change: then it is re-embedded."""
    basis = json.dumps([doc, embed_model, CHUNK_FORMAT, config.CHUNK_SIZE, config.CHUNK_OVERLAP], sort_keys=True,
                       ensure_ascii=False, default=str)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def build_chunks(scheme: dict, digest: str, embed_model: str) -> list[dict]:
    """Chunk documents (without vectors) for one scheme in engine form."""
    state = scheme.get("state") or "central"
    out = []
    for parent in scheme_sections(scheme):
        for c in split_section(parent):
            out.append({"_id": c["id"], "scheme_id": c["scheme_id"], "section": c["section"], "lang": c["lang"],
                        "state": state, "level": c["level"], "parent_id": c["parent_id"], "text": c["text"],
                        "context": parent["text"], "content_hash": digest, "embed_model": embed_model})
    return out


def index_definitions(dims: int) -> dict[str, tuple[str, dict]]:
    return {
        VECTOR_INDEX: ("vectorSearch", {"fields": [
            {"type": "vector", "path": "embedding", "numDimensions": dims, "similarity": "cosine"},
            {"type": "filter", "path": "state"},
            {"type": "filter", "path": "lang"},
            {"type": "filter", "path": "section"},
            {"type": "filter", "path": "embed_model"},
        ]}),
        TEXT_INDEX: ("search", {"mappings": {"dynamic": False, "fields": {
            "text": {"type": "string"},
            "state": {"type": "token"},
            "lang": {"type": "token"},
        }}}),
    }


def ensure_indexes(coll, dims: int) -> None:
    """Create the Atlas Vector Search and Atlas Search indexes if missing (they build in the background)."""
    from pymongo.operations import SearchIndexModel

    existing = {ix["name"]: ix for ix in coll.list_search_indexes()}
    for name, (kind, definition) in index_definitions(dims).items():
        if name not in existing:
            coll.create_search_index(SearchIndexModel(definition=definition, name=name, type=kind))
            log.info("created search index %s (%s); Atlas builds it in the background", name, kind)
        elif existing[name].get("latestDefinition") != definition:
            coll.update_search_index(name, definition)
            log.info("updated search index %s", name)


def index_status(coll) -> dict[str, str]:
    return {ix["name"]: ix.get("status", "?") for ix in coll.list_search_indexes()}


def sync(client) -> dict:
    """Bring scheme_chunks in line with the schemes collection. Returns counts."""
    emb = get_embedder()
    if emb.name == "hash":
        raise RuntimeError("the embedding model could not be loaded (hashing fallback); refusing to store "
                           "vectors that the server's model can't match. Check fastembed / MODEL_CACHE.")
    schemes_coll = client[config.MONGODB_DB][config.MONGODB_COLLECTION]
    coll = chunks_collection(client)

    valid, _ = check(list(schemes_coll.find({}, {"_id": 0})))
    keep = [s for s in valid if served(s)]
    ids = {s.id for s in keep}
    engine = {s.id: to_engine(s, ids) for s in keep}
    hashes = {s.id: content_hash(to_document(s), emb.name) for s in keep}

    stored = {g["_id"]: g["hash"] for g in coll.aggregate(
        [{"$group": {"_id": "$scheme_id", "hash": {"$first": "$content_hash"}}}])}
    stale = [sid for sid, h in stored.items() if hashes.get(sid) != h]
    removed = coll.delete_many({"scheme_id": {"$in": stale}}).deleted_count if stale else 0
    todo = [sid for sid in hashes if stored.get(sid) != hashes[sid]]

    docs = [d for sid in todo for d in build_chunks(engine[sid], hashes[sid], emb.name)]
    t = time.perf_counter()
    for i in range(0, len(docs), EMBED_BATCH):
        batch = docs[i:i + EMBED_BATCH]
        for d, vec in zip(batch, emb.embed([d["text"] for d in batch])):
            d["embedding"] = Binary.from_vector(vec, BinaryVectorDtype.FLOAT32)
        coll.insert_many(batch, ordered=False)
    if docs:
        log.info("embedded %d chunks for %d schemes in %.1fs", len(docs), len(todo), time.perf_counter() - t)

    coll.create_index("scheme_id")
    ensure_indexes(coll, emb.dim)
    return {"schemes_embedded": len(todo), "chunks_written": len(docs), "chunks_removed": removed,
            "chunks_total": coll.count_documents({}), "unchanged": len(hashes) - len(todo),
            "indexes": index_status(coll)}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    if not config.MONGODB_URI:
        print("MONGODB_URI is not set", file=sys.stderr)
        return 1
    from pymongo.errors import PyMongoError
    try:
        with db.client() as client:
            print(json.dumps(sync(client), indent=2))
    except PyMongoError as e:
        print(f"MongoDB error: {db.explain(e)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
