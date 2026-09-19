"""Dense embeddings: fastembed multilingual model, falling back to signed feature hashing.

The hashing embedder (character n-grams + words) needs no download and works for any script, but it only
captures spelling overlap. It is used when EMBED_MODEL=hash or fastembed / the model cannot be loaded.
Chunk vectors are cached per (embedder, corpus) in search.py, so switching backends re-embeds the corpus.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
from functools import lru_cache

from app.core import config

log = logging.getLogger("urimai.retrieval")
_WORD = re.compile(r"\w+", re.UNICODE)


def _features(text: str):
    words = _WORD.findall(text.lower())
    for w in words:
        yield "w:" + w, 1.0
        padded = f"#{w}#"
        for n in (3, 4):
            for i in range(len(padded) - n + 1):
                yield f"c{n}:" + padded[i:i + n], 0.5
    for a, b in zip(words, words[1:]):
        yield f"b:{a}_{b}", 0.7


def hash_embed(text: str, dim: int = config.HASH_DIM) -> list[float]:
    vec = [0.0] * dim
    for feat, weight in _features(text):
        h = int.from_bytes(hashlib.md5(feat.encode("utf-8")).digest()[:8], "little")
        vec[h % dim] += weight if (h >> 63) & 1 else -weight
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # vectors are L2-normalised


class Embedder:
    def __init__(self, model_name: str = config.EMBED_MODEL):
        self.model = None
        self.name = "hash"
        if model_name.lower() not in ("hash", "none", ""):
            try:
                import warnings

                from fastembed import TextEmbedding
                with warnings.catch_warnings():  # "now uses mean pooling": that is the correct pooling
                    warnings.simplefilter("ignore", UserWarning)
                    self.model = TextEmbedding(model_name, cache_dir=config.MODEL_CACHE)
                self.name = model_name
            except Exception as e:  # not installed, offline on first run, unknown model
                log.warning("dense model %s unavailable (%s); using hashing embedder", model_name, e)
        self.dim = len(self.embed(["probe"])[0])

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.model is None:
            return [hash_embed(t) for t in texts]
        out = []
        for v in self.model.embed(texts):
            n = float((v ** 2).sum()) ** 0.5 or 1.0
            out.append((v / n).tolist())
        return out


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder()


def embed(text: str) -> list[float]:
    return get_embedder().embed([text])[0]
