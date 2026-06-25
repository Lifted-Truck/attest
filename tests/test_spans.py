"""Standing tests for the span store + resolution invariant (ROADMAP M1-T2).

Covers: get_span returns the exact slice and re-verifies the doc hash (I3),
chunking is deterministic (I6), and every golden verbatim_quote resolves to
exactly one location in the canonical text (the resolution invariant, D7) and
binds to a span.
"""

import json
from pathlib import Path

import pytest

from attest.ingest import DocumentStore, HashMismatch
from attest.ingest.document import Document
from attest.spans import ResolutionError, SpanError, SpanStore, chunk_document

ROOT = Path(__file__).resolve().parent.parent
DOC_ID = "AAPL-10K-FY2024"


@pytest.fixture(scope="module")
def store() -> SpanStore:
    ds = DocumentStore(ROOT / "corpus" / "store")
    if DOC_ID not in ds.list_docs():
        pytest.skip("corpus not ingested — run scripts/ingest_corpus.py")
    return SpanStore.from_store(ds)


@pytest.fixture(scope="module")
def golden() -> list[dict]:
    return json.loads((ROOT / "golden_seed.json").read_text(encoding="utf-8"))["items"]


def test_get_span_returns_exact_slice(store):
    sp = store.spans(DOC_ID)[0]
    assert store.get_span(DOC_ID, sp.char_start, sp.char_end) == sp.text


def test_every_span_offset_is_consistent(store):
    """canonical_text[start:end] == span.text for every span."""
    for sp in store.spans(DOC_ID):
        assert store.get_span(DOC_ID, sp.char_start, sp.char_end) == sp.text


def test_get_span_reverifies_doc_hash(store):
    """I3: a document whose text no longer matches its hash refuses to serve spans."""
    real = store._docs[DOC_ID]
    drifted = Document(real.doc_id, real.canonical_text, "0" * 64, real.metadata)
    bad_store = SpanStore([drifted])
    with pytest.raises(HashMismatch):
        bad_store.get_span(DOC_ID, 0, 10)


def test_get_span_out_of_range_rejected(store):
    n = len(store._docs[DOC_ID].canonical_text)
    with pytest.raises(SpanError):
        store.get_span(DOC_ID, 0, n + 1)
    with pytest.raises(SpanError):
        store.get_span(DOC_ID, 50, 10)


def test_chunking_is_deterministic(store):
    """I6: same canonical text → identical spans, identical offsets."""
    doc = store._docs[DOC_ID]
    assert chunk_document(doc) == chunk_document(doc)


def test_resolution_invariant_on_golden_quotes(store, golden):
    """D7: every golden verbatim_quote resolves to exactly one span."""
    bound = 0
    for item in golden:
        for s in item.get("supporting", []):
            quote = s.get("verbatim_quote")
            if not quote:
                continue
            start, _end = store.resolve_quote(DOC_ID, quote)  # raises if not exactly 1
            assert store.span_containing(DOC_ID, start), f"{item['id']}: no span for quote"
            bound += 1
    assert bound >= 18, f"expected the golden set's quotes to be bound, only saw {bound}"


def test_answerable_items_are_fully_bound(store, golden):
    """Every answerable item carries at least one resolvable verbatim_quote."""
    for item in golden:
        if item["answerable"]:
            quotes = [s.get("verbatim_quote") for s in item["supporting"]]
            assert any(quotes), f"{item['id']} is answerable but has no verbatim_quote"
            for q in filter(None, quotes):
                store.resolve_quote(DOC_ID, q)


def test_duplicate_quote_fails_resolution(store):
    """A non-unique quote is a hard failure (protects against silent ambiguity)."""
    with pytest.raises(ResolutionError):
        store.resolve_quote(DOC_ID, "Ernst & Young LLP")  # appears 4×


def test_missing_quote_fails_resolution(store):
    with pytest.raises(ResolutionError):
        store.resolve_quote(DOC_ID, "Microsoft Azure revenue by segment")
