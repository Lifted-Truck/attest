"""Standing tests for the patent claim model (PE-1, first increment).

Deterministic structural parsing over the shared canonical text — no model. Uses a
synthetic sample patent so it is hermetic and free of confidentiality/copyright.
"""

from pathlib import Path

from attest.ingest import DocumentStore
from attest.ingest.files import ingest_paths
from attest.patents import parse_claims
from attest.spans import SpanStore

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "corpus" / "samples" / "sample_patent.txt"


def _text() -> str:
    return SAMPLE.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_parses_claims_with_dependency():
    claims = parse_claims(_text())
    assert [c.number for c in claims] == [1, 2, 3, 4, 5]
    assert [c.kind for c in claims] == [
        "independent", "dependent", "dependent", "independent", "dependent",
    ]
    assert [c.depends_on for c in claims] == [None, 1, 2, None, 4]


def test_claim_offsets_are_self_addressable():
    text = _text()
    claims = parse_claims(text)
    for c in claims:
        assert text[c.char_start:c.char_end] == c.text     # offsets are exact
        assert c.text.startswith(f"{c.number}.")           # starts at the claim number


def test_claim_spans_resolve_through_the_span_store(tmp_path):
    """Builds on the shared engine: each claim is a real, hash-verified span (I3)."""
    store_dir = tmp_path / "store"
    ingest_paths([str(SAMPLE)], store_dir, kind="patent")
    store = SpanStore.from_store(DocumentStore(store_dir))
    doc = SAMPLE.stem
    text = store.get_document(doc)
    for c in parse_claims(text):
        assert store.get_span(doc, c.char_start, c.char_end) == c.text


def test_no_claims_section_returns_empty():
    assert parse_claims("A document with no claims section at all.") == []
