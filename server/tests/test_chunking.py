"""Recursive chunker + parent/child chunk building (app/retrieval). Pure functions, no models."""
from app.retrieval.chunking import recursive_split
from app.retrieval.docs import all_chunks, all_sections


def test_short_text_is_one_chunk():
    assert recursive_split("one line", 50, 10) == ["one line"]
    assert recursive_split("   ", 50, 10) == []


def test_chunks_respect_size_and_split_at_coarsest_boundary():
    text = "Para one. Sentence two.\n\nPara two " + "word " * 30
    chunks = recursive_split(text, 60, 15)
    assert all(len(c) <= 60 for c in chunks)
    assert chunks[0] == "Para one. Sentence two."  # paragraph boundary kept whole


def test_overlap_carries_text_into_next_chunk():
    chunks = recursive_split(" ".join(f"w{i}" for i in range(40)), 40, 12)
    assert all(len(c) <= 40 for c in chunks)
    assert all(a.split()[-1] in b for a, b in zip(chunks, chunks[1:]))


def test_numbered_steps_are_not_split_from_their_text():
    chunks = recursive_split("1. Register on the portal with your details today\n2. Complete e-KYC", 40, 0)
    assert "1." not in chunks and all(not c.endswith(" 1.") for c in chunks)


def test_every_child_has_header_and_parent():
    parents = {p["id"]: p for p in all_sections()}
    chunks = all_chunks()
    assert len(chunks) >= len(parents) >= 150
    for c in chunks:
        assert c["parent_id"] in parents and " | " in c["text"].split("\n", 1)[0]
    assert {c["section"] for c in chunks} == {"overview", "eligibility", "documents", "how_to_apply"}
