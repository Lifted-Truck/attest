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


class _OkResult:
    """Minimal VerifyResult stand-in: verify_record reads only .ok and .unbound()."""
    ok = True

    def unbound(self):
        return []


def test_records_carry_contract_provenance_and_replay(retriever):
    """TC-2/D21: records stamp contract_version + methods, and still replay (I6)."""
    from attest.contract import CONTRACT_VERSION
    from attest.session import verify_record

    q = "How much term debt does Apple carry?"
    rec = support_record(q, check_support(q, retriever), threshold=15.0,
                         retrieval=retriever.method)
    assert rec["provenance"] == {"contract": CONTRACT_VERSION, "retrieval": "bm25",
                                 "threshold": 15.0}
    assert replays_identically(rec, retriever)            # stamp round-trips byte-identical

    # a non-default floor is recorded and replays under that floor, not the default
    loose = support_record(q, check_support(q, retriever, threshold=1.0), threshold=1.0,
                           retrieval=retriever.method)
    assert loose["provenance"]["threshold"] == 1.0
    assert replays_identically(loose, retriever)

    vr = verify_record({"sentences": [{"text": "x", "atoms": []}]}, _OkResult())
    assert vr["provenance"]["contract"] == CONTRACT_VERSION
    assert "verify_ops" in vr["provenance"]
