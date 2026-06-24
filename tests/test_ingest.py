"""Standing I3 tests for ingestion (ROADMAP M1-T1).

I3 — verified immutability of source: every stored doc carries its hash, the
hash re-verifies on load, and any drift is a hard failure. Also checks the
adapter is deterministic (I6) and that normalization preserved the evidence the
golden set resolves against.
"""

from pathlib import Path

import pytest

from attest.ingest import Document, DocumentStore, HashMismatch, content_hash, verify_document
from attest.ingest.edgar import FILINGS, normalize

ROOT = Path(__file__).resolve().parent.parent
STORE = DocumentStore(ROOT / "corpus" / "store")
RAW = ROOT / "data" / "raw"
DOC_ID = "AAPL-10K-FY2024"


@pytest.fixture(scope="module")
def doc() -> Document:
    if DOC_ID not in STORE.list_docs():
        pytest.skip("corpus not ingested — run scripts/ingest_corpus.py")
    return STORE.load(DOC_ID)


def test_stored_doc_carries_and_matches_its_hash(doc):
    """I3: the committed canonical text hashes to the stored content_hash."""
    assert doc.content_hash == content_hash(doc.canonical_text)
    verify_document(doc)  # does not raise


def test_tampered_text_is_rejected(doc):
    """I3: a one-character drift from the stored hash is a hard failure."""
    tampered = Document(doc.doc_id, doc.canonical_text + " ", doc.content_hash, doc.metadata)
    with pytest.raises(HashMismatch):
        verify_document(tampered)


def test_tampered_hash_is_rejected(doc):
    bad = Document(doc.doc_id, doc.canonical_text, "0" * 64, doc.metadata)
    with pytest.raises(HashMismatch):
        verify_document(bad)


def test_provenance_recorded(doc):
    meta = doc.metadata
    for field in ("ticker", "form", "accession", "cik", "period_of_report", "primary_url"):
        assert meta.get(field), f"missing provenance field: {field}"
    assert meta["form"] == "10-K"


def test_normalization_is_deterministic(doc):
    """I6: same raw HTML → identical canonical text → identical hash."""
    raw_path = RAW / FILINGS[DOC_ID]["primary_document"]
    if not raw_path.exists():
        pytest.skip("raw filing not cached — run scripts/ingest_corpus.py")
    raw = raw_path.read_text(encoding="utf-8")
    first, second = normalize(raw), normalize(raw)
    assert first == second
    assert content_hash(first) == doc.content_hash  # matches what was committed


# Figures / strings the answerable golden items rest on must survive normalization.
GOLDEN_EVIDENCE = [
    "Total assets $ 364,980 $ 352,583",
    "176,392", "9,967", "45,680", "78,304", "14,287", "8,249",
    "10,912", "9,822", "85,750", "91,479",
    "For the fiscal year ended September 28, 2024",
    "Ernst & Young LLP",
]


def test_canonical_preserves_golden_evidence(doc):
    missing = [s for s in GOLDEN_EVIDENCE if s not in doc.canonical_text]
    assert not missing, f"normalization dropped golden evidence: {missing}"
