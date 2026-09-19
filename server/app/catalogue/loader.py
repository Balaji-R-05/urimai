"""Load the scheme catalogue (central and state schemes) and turn it into the form the engine uses.

Source: the MongoDB collection when MONGODB_URI is set, otherwise the bundled seed file data/schemes.json.
Every document is checked against the schema (app/catalogue/schema.py):
  - seed file: any error stops startup (the bundled data must be clean);
  - MongoDB: invalid documents are logged and skipped, so one bad record can't take the bot down.
Only active, non-draft schemes are served. Seed MongoDB with:  python -m app.catalogue.seed
Loaded once per process; restart the server to pick up catalogue changes.
"""
from __future__ import annotations

import json
import logging
import time
from functools import lru_cache
from pathlib import Path

from app.catalogue.schema import Scheme, check, to_document
from app.core import config
from app.domain.fields import lives_in

log = logging.getLogger("urimai.catalogue")

SEED = config.SEED_PATH


class CatalogueError(ValueError):
    pass


def read_seed(path: Path = SEED) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


READ_ATTEMPTS = 3


def _read_mongo() -> list[dict]:
    """All scheme documents. Retries a few times: a short network drop shouldn't stop the bot starting."""
    from pymongo.errors import PyMongoError

    from app.core import db

    for attempt in range(1, READ_ATTEMPTS + 1):
        client = db.client(timeout_ms=10000)
        try:
            coll = client[config.MONGODB_DB][config.MONGODB_COLLECTION]
            schemes = list(coll.find({}, {"_id": 0}).sort("id", 1))
            break
        except PyMongoError as e:
            if attempt == READ_ATTEMPTS:
                raise CatalogueError(f"cannot read schemes from MongoDB: {db.explain(e)}") from e
            log.warning("reading schemes failed (attempt %d/%d): %s; retrying", attempt, READ_ATTEMPTS,
                        db.explain(e))
            time.sleep(2 * attempt)
        finally:
            client.close()
    if not schemes:
        raise CatalogueError(f"MongoDB collection '{config.MONGODB_DB}.{config.MONGODB_COLLECTION}' is empty; "
                             "run: python -m app.catalogue.seed")
    return schemes


def served(s: Scheme) -> bool:
    """Shown to users: active and past draft review."""
    return s.status == "active" and s.verification.status != "draft"


def to_engine(s: Scheme, loaded_ids: set[str]) -> dict:
    """The dict the rule engine, planner and replies read. State schemes get a residence rule prepended."""
    d = to_document(s)
    elig = d["eligibility"]
    for block in ("all", "any", "none", "other"):
        elig.setdefault(block, [])
    if s.state:
        elig["all"].insert(0, {"field": "state", "op": "eq", "value": s.state, "text": lives_in(s.state)})
    docs = d.get("documents", [])
    d["documents"] = [x if isinstance(x, str) else x["id"] for x in docs]
    d["document_labels"] = {x["id"]: x["label"] for x in docs if isinstance(x, dict)}
    d["source_url"] = s.source.url
    d["unverified"] = s.verification.status != "verified"
    # a draft or closed partner isn't loaded, so there's nothing to conflict with
    d["mutually_exclusive_with"] = [x for x in s.mutually_exclusive_with if x in loaded_ids]
    return d


def validate(docs: list[dict], strict: bool = True) -> list[dict]:
    """Validate raw documents and return the served schemes in engine form.
    strict: raise on any invalid document; otherwise log and skip it."""
    valid, errors = check(docs)
    if errors:
        lines = [f"{sid}: {e}" for sid, errs in errors.items() for e in errs]
        if strict:
            raise CatalogueError(f"{len(errors)} invalid scheme(s):\n  " + "\n  ".join(lines))
        log.warning("skipped %d invalid scheme(s):\n  %s", len(errors), "\n  ".join(lines))
    keep = [s for s in valid if served(s)]
    ids = {s.id for s in keep}
    if not keep:
        raise CatalogueError("no servable schemes (all invalid, draft or closed)")
    log.info("catalogue: %d schemes served (%d draft/closed, %d invalid)", len(keep), len(valid) - len(keep),
             len(errors))
    return [to_engine(s, ids) for s in keep]


@lru_cache(maxsize=1)
def load_schemes() -> list[dict]:
    """The served catalogue, shared by the engine, the extractor and retrieval. Treat as read-only."""
    if config.MONGODB_URI:
        return validate(_read_mongo(), strict=False)
    return validate(read_seed(), strict=True)
