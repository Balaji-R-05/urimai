"""Load a scheme JSON file into MongoDB (upsert by scheme id). Run from server/:

    python -m app.catalogue.seed --dry-run schemes.json   # check a file against the schema, write nothing
    python -m app.catalogue.seed                          # data/schemes.json -> MONGODB_URI
    python -m app.catalogue.seed more.json                # add or update schemes from another file
    python -m app.catalogue.seed more.json --replace      # also delete stored schemes that are not in the file
    python -m app.catalogue.seed big.json --strict        # write nothing if any scheme is invalid
    python -m app.catalogue.seed --no-chunks              # skip updating scheme search (scheme_chunks)

Every scheme is checked against app/catalogue/schema.py. Valid schemes are written; invalid ones are listed
with the reason and skipped. Schemes marked verification.status = "draft" are stored but not shown to users.
Afterwards the scheme search collection (scheme_chunks) is brought up to date: changed schemes are re-embedded
and the Atlas search indexes are created if missing (app/retrieval/chunk_store.py).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from collections import Counter
from pathlib import Path

from app.catalogue.loader import SEED, read_seed, served
from app.catalogue.schema import check, to_document
from app.core import config

MAX_ERRORS_SHOWN = 50


def report(valid, errors) -> None:
    for n, (sid, errs) in enumerate(errors.items()):
        if n == MAX_ERRORS_SHOWN:
            print(f"  ... and {len(errors) - n} more invalid schemes")
            break
        for e in errs:
            print(f"  ✗ {sid}: {e}")
    states = Counter(s.verification.status for s in valid)
    levels = Counter(s.state or "central" for s in valid)
    print(f"{len(valid)} valid, {len(errors)} invalid  |  served: {sum(served(s) for s in valid)}  "
          f"({', '.join(f'{k} {v}' for k, v in sorted(states.items()))})  |  "
          + ", ".join(f"{k} {v}" for k, v in levels.most_common()))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", type=Path, default=SEED)
    ap.add_argument("--dry-run", action="store_true", help="validate only; write nothing")
    ap.add_argument("--strict", action="store_true", help="write nothing if any scheme is invalid")
    ap.add_argument("--replace", action="store_true", help="delete stored schemes whose id is not in the file")
    ap.add_argument("--no-chunks", action="store_true", help="don't update scheme search (scheme_chunks)")
    a = ap.parse_args()

    try:
        docs = read_seed(a.file)
    except (OSError, json.JSONDecodeError) as e:
        print(f"cannot read {a.file}: {e}", file=sys.stderr)
        return 1
    if not isinstance(docs, list):
        print(f"{a.file}: expected a JSON array of schemes", file=sys.stderr)
        return 1

    valid, errors = check(docs)
    print(f"{a.file.name}: {len(docs)} schemes")
    report(valid, errors)
    if a.dry_run:
        return 1 if errors else 0
    if errors and a.strict:
        print("--strict: nothing written", file=sys.stderr)
        return 1
    if not valid:
        return 1
    if not config.MONGODB_URI:
        print("MONGODB_URI is not set (see .env.example)", file=sys.stderr)
        return 1

    from pymongo.errors import PyMongoError

    from app.core import db
    now = dt.datetime.now(dt.timezone.utc)
    try:
        return _write(a, valid, errors, now)
    except PyMongoError as e:
        print(f"MongoDB error: {db.explain(e)}", file=sys.stderr)
        return 1


def _write(a, valid, errors, now) -> int:
    from pymongo import ReplaceOne

    from app.core import db
    with db.client() as client:
        coll = client[config.MONGODB_DB][config.MONGODB_COLLECTION]
        coll.create_index("id", unique=True)
        res = coll.bulk_write([ReplaceOne({"id": s.id}, {**to_document(s), "updated_at": now}, upsert=True)
                               for s in valid])
        removed = coll.delete_many({"id": {"$nin": [s.id for s in valid]}}).deleted_count if a.replace else 0
        total = coll.count_documents({})
        print(f"{config.MONGODB_DB}.{config.MONGODB_COLLECTION}: {res.upserted_count} added, "
              f"{res.modified_count} updated, {removed} removed, {total} total")
        if not a.no_chunks:
            from app.retrieval import chunk_store
            c = chunk_store.sync(client)
            print(f"{config.MONGODB_DB}.{config.MONGODB_CHUNKS_COLLECTION}: {c['schemes_embedded']} schemes embedded "
                  f"({c['chunks_written']} chunks), {c['unchanged']} unchanged, {c['chunks_removed']} chunks removed, "
                  f"{c['chunks_total']} total  |  search indexes: "
                  + ", ".join(f"{k} {v}" for k, v in c["indexes"].items()))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
