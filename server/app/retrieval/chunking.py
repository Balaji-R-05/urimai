"""Recursive character splitter (LangChain-style, no dependency).

Try the coarsest separator first (paragraph, line, sentence, clause, word). Any piece still longer than
`size` is split again with the next separator. Small pieces are then merged back up to `size`, with
`overlap` characters carried into the next chunk so a fact on a boundary appears whole in at least one chunk.
"""
from __future__ import annotations

import re

SEPARATORS = ("\n\n", "\n", ". ", "। ", "; ", ", ", " ", "")


_SENTENCE = re.compile(r"(?<=\D\. )")  # after ". ", but not "1. " (numbered steps stay with their text)


def _split(text: str, sep: str) -> list[str]:
    if sep == "":
        return list(text)
    if sep == ". ":
        return [p for p in _SENTENCE.split(text) if p]
    parts = text.split(sep)
    # keep the separator attached to the left piece so merged chunks read naturally
    return [p + sep for p in parts[:-1]] + [parts[-1]]


def _merge(pieces: list[str], size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for p in pieces:
        if cur and cur_len + len(p) > size:
            chunks.append("".join(cur).strip())
            # drop pieces from the front until what is left fits in the overlap budget
            while cur and (cur_len > overlap or cur_len + len(p) > size):
                cur_len -= len(cur.pop(0))
        cur.append(p)
        cur_len += len(p)
    if cur:
        chunks.append("".join(cur).strip())
    return [c for c in chunks if c]


def recursive_split(text: str, size: int = 300, overlap: int = 60,
                    separators: tuple[str, ...] = SEPARATORS) -> list[str]:
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    sep = next((s for s in separators if s == "" or s in text), "")
    rest = separators[separators.index(sep) + 1:] if sep else ()
    out: list[str] = []
    good: list[str] = []  # pieces that fit, waiting to be merged
    for p in _split(text, sep):
        if len(p) <= size:
            good.append(p)
            continue
        out.extend(_merge(good, size, overlap))
        good = []
        out.extend(recursive_split(p, size, overlap, rest) if rest else [p.strip()])
    out.extend(_merge(good, size, overlap))
    return out
