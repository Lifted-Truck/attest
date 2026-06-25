"""Standing tests for verify — the atom resolver (ROADMAP M2-T1, D9, I1).

Covers the AC: a planted unbound claim is flagged; a clean answer passes; the
result is a complete record. Plus mismatch, derived recomputation, hash-drift
(I3), and out-of-range bindings.
"""

from pathlib import Path

import pytest

from attest.ingest import DocumentStore
from attest.spans import SpanStore
from attest.verify import Answer, AtomBinding, DerivedAtom, Sentence, verify

ROOT = Path(__file__).resolve().parent.parent
DOC_ID = "AAPL-10K-FY2024"
TOTAL_ASSETS = "Total assets $ 364,980 $ 352,583"


@pytest.fixture(scope="module")
def store() -> SpanStore:
    ds = DocumentStore(ROOT / "corpus" / "store")
    if DOC_ID not in ds.list_docs():
        pytest.skip("corpus not ingested — run scripts/ingest_corpus.py")
    return SpanStore.from_store(ds)


def bind(
    store: SpanStore, literal: str, line: str, *, content_hash: str | None = None
) -> AtomBinding:
    """Bind a figure to its exact offset within a (uniquely resolvable) line."""
    line_start, _ = store.resolve_quote(DOC_ID, line)
    idx = line.index(literal)
    start = line_start + idx
    return AtomBinding(literal, DOC_ID, start, start + len(literal), content_hash)


def test_clean_answer_passes(store):
    h = store._docs[DOC_ID].content_hash
    ans = Answer([
        Sentence(
            "Apple's total assets were $364,980 million.",
            atoms=[bind(store, "364,980", TOTAL_ASSETS, content_hash=h)],
        )
    ])
    result = verify(ans, store)
    assert result.ok
    assert result.sentences[0].atom_verdicts[0].status == "ok"
    assert not result.unbound()


def test_planted_unbound_claim_is_flagged(store):
    """The AC: a figure asserted with no binding cannot slip through."""
    ans = Answer([Sentence("Apple's total assets were $999,999 million.", atoms=[])])
    result = verify(ans, store)
    assert not result.ok
    assert "999,999" in result.unbound()


def test_wrong_offset_is_mismatch(store):
    """Binding the figure to the wrong column (352,583's slot) is caught."""
    good = bind(store, "364,980", TOTAL_ASSETS)
    wrong = AtomBinding("364,980", DOC_ID, good.char_start + 10, good.char_end + 10)
    ans = Answer([Sentence("Total assets were $364,980 million.", atoms=[wrong])])
    result = verify(ans, store)
    assert not result.ok
    assert result.sentences[0].atom_verdicts[0].status == "mismatch"


def test_stale_hash_is_flagged(store):
    """A binding made against a different doc version (hash) is rejected (I3)."""
    real = bind(store, "364,980", TOTAL_ASSETS)
    stale = AtomBinding(
        real.text, real.doc_id, real.char_start, real.char_end, content_hash="0" * 64
    )
    ans = Answer([Sentence("Total assets were $364,980 million.", atoms=[stale])])
    result = verify(ans, store)
    assert not result.ok
    assert result.sentences[0].atom_verdicts[0].status == "stale_hash"


def test_out_of_range_is_flagged(store):
    n = len(store.get_document(DOC_ID))
    ans = Answer([Sentence("x $1,234 y", atoms=[AtomBinding("1,234", DOC_ID, n + 1, n + 6)])])
    result = verify(ans, store)
    assert result.sentences[0].atom_verdicts[0].status == "out_of_range"


def test_derived_value_recomputes(store):
    """G005: the $12,397M delta is recomputed from bound operands, not cited."""
    sent = Sentence(
        "Total assets increased by $12,397 million (from $352,583M to $364,980M).",
        derived=[DerivedAtom(
            "12,397", "subtract",
            [bind(store, "364,980", TOTAL_ASSETS), bind(store, "352,583", TOTAL_ASSETS)],
        )],
    )
    result = verify(Answer([sent]), store)
    assert result.ok
    assert not result.unbound()


def test_wrong_derived_value_is_flagged(store):
    sent = Sentence(
        "Total assets increased by $12,398 million (from $352,583M to $364,980M).",
        derived=[DerivedAtom(
            "12,398", "subtract",
            [bind(store, "364,980", TOTAL_ASSETS), bind(store, "352,583", TOTAL_ASSETS)],
        )],
    )
    result = verify(Answer([sent]), store)
    assert not result.ok
