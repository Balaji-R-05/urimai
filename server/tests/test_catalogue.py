"""Catalogue sources: JSON seed by default, MongoDB when MONGODB_URI is set (client stubbed, no server needed)."""
import copy

import pytest

from app.catalogue import loader
from app.catalogue.loader import CatalogueError, load_schemes, read_seed
from app.core import config, db


class _Cursor(list):
    def sort(self, key, direction=1):
        return _Cursor(sorted(self, key=lambda d: d[key], reverse=direction < 0))


class _Collection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, _filter, projection):
        return _Cursor({k: v for k, v in d.items() if projection.get(k, 1)} for d in copy.deepcopy(self.docs))


@pytest.fixture
def mongo(monkeypatch):
    """Point the catalogue at a fake MongoDB holding `docs`; returns the docs list to fill."""
    docs: list[dict] = []

    class FakeClient:
        def __getitem__(self, name):
            assert name == config.MONGODB_DB
            return {config.MONGODB_COLLECTION: _Collection(docs)}

        def close(self):
            pass

    monkeypatch.setattr(db, "client", lambda timeout_ms=5000: FakeClient())
    monkeypatch.setattr(config, "MONGODB_URI", "mongodb://test")
    load_schemes.cache_clear()
    yield docs
    load_schemes.cache_clear()


def test_default_source_is_the_json_seed():
    assert [s["id"] for s in load_schemes()] == [s["id"] for s in read_seed()]


def test_mongo_source_is_validated_like_the_seed(mongo):
    mongo.extend({"_id": i, **s} for i, s in enumerate(read_seed()))
    schemes = load_schemes()
    assert {s["id"] for s in schemes} == {s["id"] for s in read_seed()}
    assert all("_id" not in s for s in schemes)
    kmut = next(s for s in schemes if s["id"] == "kmut")
    assert kmut["eligibility"]["all"][0]["field"] == "state"  # residence rule added for state schemes


def test_empty_mongo_collection_fails_loudly(mongo):
    with pytest.raises(CatalogueError, match="app.catalogue.seed"):
        load_schemes()


def test_other_state_scheme_gets_its_own_residence_rule(mongo):
    s = copy.deepcopy(next(s for s in read_seed() if s.get("state") == "TN"))
    mongo.append({**s, "id": "kl_demo", "state": "KL", "mutually_exclusive_with": []})
    rule = load_schemes()[0]["eligibility"]["all"][0]
    assert rule["value"] == "KL" and rule["text"]["en"] == "Lives in KL"


def test_bad_scheme_is_rejected():
    bad = copy.deepcopy(read_seed()[:1])
    bad[0]["eligibility"]["all"].append({"field": "shoe_size", "op": "eq", "value": 9})
    with pytest.raises(CatalogueError, match="shoe_size"):
        loader.validate(bad)
