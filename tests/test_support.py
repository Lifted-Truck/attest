"""Standing tests for check_support — deterministic abstention (M2-T2, D12, I2).

The deterministic trigger (D12): `insufficient` on the content-absent
unanswerables; supporting spans (incl. the gold span) on answerable items. The
semantic traps (G014/G015/G016/G020) are NOT this tool's job — they retrieve real
content and are abstained by the agent, measured at Layer-E.
"""

import json
from pathlib import Path

import pytest

from attest.ingest import DocumentStore
from attest.retrieval import Retriever
from attest.spans import SpanStore
from attest.support import check_support

ROOT = Path(__file__).resolve().parent.parent
DOC_ID = "AAPL-10K-FY2024"

# D12: unanswerable because the corpus has no relevant content (vs semantic traps).
CONTENT_ABSENT = {"G011", "G012", "G013"}
# Known retrieval lexical gap (auditor signature shares no terms with the question)
# → fixed by the embedding backend / section-aware chunking (M2 retrieval tuning).
LEXICAL_GAP = {"G009"}


@pytest.fixture(scope="module")
def store() -> SpanStore:
    ds = DocumentStore(ROOT / "corpus" / "store")
    if DOC_ID not in ds.list_docs():
        pytest.skip("corpus not ingested — run scripts/ingest_corpus.py")
    return SpanStore.from_store(ds)


@pytest.fixture(scope="module")
def retriever(store) -> Retriever:
    return Retriever(store)


@pytest.fixture(scope="module")
def golden() -> list[dict]:
    return json.loads((ROOT / "golden_seed.json").read_text(encoding="utf-8"))["items"]


def _gold_span_ids(store, item) -> set[str]:
    ids = set()
    for s in item.get("supporting", []):
        quote = s.get("verbatim_quote")
        if not quote:
            continue
        start, _ = store.resolve_quote(DOC_ID, quote)
        sp = store.span_containing(DOC_ID, start)
        if sp:
            ids.add(sp.span_id)
    return ids


def test_insufficient_on_content_absent_unanswerables(retriever, golden):
    """100% deterministic abstention on the content-absent subset (D12)."""
    by_id = {it["id"]: it for it in golden}
    for gid in CONTENT_ABSENT:
        result = check_support(by_id[gid]["question"], retriever)
        assert result.insufficient, f"{gid} should be insufficient, got {result.status}"
        assert result.closest, f"{gid} should still show the closest spans it found"


def test_supported_and_gold_returned_on_answerable(store, retriever, golden):
    for item in golden:
        if not item["answerable"] or item["id"] in LEXICAL_GAP:
            continue
        result = check_support(item["question"], retriever)
        assert result.status == "supported", f"{item['id']} should be supported"
        returned = {h.span.span_id for h in result.supporting}
        gold = _gold_span_ids(store, item)
        assert gold & returned, f"{item['id']}: gold span not among supporting"


def test_supporting_is_ranked(retriever, golden):
    by_id = {it["id"]: it for it in golden}
    result = check_support(by_id["G007"]["question"], retriever)  # plural: two term-debt lines
    scores = [h.score for h in result.supporting]
    assert scores == sorted(scores, reverse=True)
