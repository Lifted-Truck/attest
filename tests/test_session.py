"""Standing tests for interaction record + replay (ROADMAP M3-T2; I5, I6)."""

from pathlib import Path

import pytest

from attest.audit import AuditLog
from attest.ingest import DocumentStore
from attest.retrieval import Retriever
from attest.session import replay_support, replays_identically, support_record
from attest.spans import SpanStore
from attest.support import check_support

ROOT = Path(__file__).resolve().parent.parent
DOC_ID = "AAPL-10K-FY2024"


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    ds = DocumentStore(ROOT / "corpus" / "store")
    if DOC_ID not in ds.list_docs():
        pytest.skip("corpus not ingested — run scripts/ingest_corpus.py")
    return Retriever(SpanStore.from_store(ds))


def test_logged_interaction_replays_byte_identically(retriever, tmp_path):
    """I5+I6: log an interaction, then reconstruct it from the log alone."""
    q = "How much term debt does Apple carry?"
    record = support_record(q, check_support(q, retriever))

    log = AuditLog(tmp_path / "audit.jsonl")
    log.append(record)
    log.verify_chain()

    replayed_payload = log.entries()[0].payload
    assert replays_identically(replayed_payload, retriever)  # re-derived == logged


def test_replay_of_abstention_matches(retriever, tmp_path):
    q = "What is Apple's customer churn rate?"  # content-absent → insufficient
    record = support_record(q, check_support(q, retriever))
    assert record["status"] == "insufficient"
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append(record)
    assert replay_support(log.entries()[0].payload, retriever) == record


def test_replay_detects_a_changed_query(retriever):
    """Replaying re-derives from the query, so a doctored query won't reproduce."""
    q = "How much term debt does Apple carry?"
    record = support_record(q, check_support(q, retriever))
    tampered = {**record, "query": "What were Apple's total assets?"}
    assert not replays_identically(tampered, retriever)
