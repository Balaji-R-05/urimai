import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.core import config  # noqa: E402

# Tests always run on the bundled JSON seed, even when .env points the server at MongoDB.
# Set before anything imports the catalogue (it is loaded once and cached).
config.MONGODB_URI = ""
config.RETRIEVAL_BACKEND = "memory"


@pytest.fixture(autouse=True)
def _no_retrieval_models(monkeypatch):
    """Unit tests never load the embedding / reranker models; test_retrieval.py stubs the search."""
    monkeypatch.setattr(config, "RETRIEVAL_ENABLED", False)
