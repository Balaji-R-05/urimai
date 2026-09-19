"""Tiny Okapi BM25 over words + character 4-grams.

The 4-grams let Tamil / Hindi inflections (ஓய்வூதியம் / ஓய்வூதியத்தை) still share terms, and catch
partial matches like "kisan" in "pm-kisan". Corpus is a few hundred chunks, so it lives in memory.
"""
from __future__ import annotations

import math
import re
from collections import Counter

_WORD = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    toks = []
    for w in _WORD.findall(text.lower()):
        toks.append(w)
        if len(w) > 4:
            toks.extend("#" + w[i:i + 4] for i in range(len(w) - 3))
    return toks


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(tokenize(d)) for d in docs]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = sum(self.len) / max(len(docs), 1)
        df = Counter(term for t in self.tf for term in t)
        n = len(docs)
        self.idf = {term: math.log(1 + (n - f + 0.5) / (f + 0.5)) for term, f in df.items()}

    def scores(self, query: str) -> list[float]:
        q = [t for t in set(tokenize(query)) if t in self.idf]
        out = []
        for tf, dl in zip(self.tf, self.len):
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avg))
            out.append(s)
        return out
