"""Standing I4 test — read/write asymmetry (ROADMAP M3-T3).

The corpus is read-only to the agent; the only writable surface is the append-only
audit log. Here: the agent-facing read path (get_document / get_span / retrieval /
check_support / verify) never mutates the corpus, and those read classes expose no
corpus mutator. (Ingestion's offline DocumentStore.write is not an agent tool;
the M4 tool boundary, M4-T3, withholds it from the agent.)
"""

import hashlib
from pathlib import Path

import pytest

from attest.audit import AuditLog
from attest.ingest import DocumentStore
from attest.retrieval import Retriever
from attest.spans import SpanStore
from attest.support import check_support

ROOT = Path(__file__).resolve().parent.parent
STORE_DIR = ROOT / "corpus" / "store"
DOC_ID = "AAPL-10K-FY2024"


def _corpus_fingerprint() -> dict[str, str]:
    return {
        str(p.relative_to(STORE_DIR)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(STORE_DIR.rglob("*")) if p.is_file()
    }


@pytest.fixture(scope="module")
def store() -> SpanStore:
    ds = DocumentStore(STORE_DIR)
    if DOC_ID not in ds.list_docs():
        pytest.skip("corpus not ingested — run scripts/ingest_corpus.py")
    return SpanStore.from_store(ds)


def test_reads_do_not_mutate_the_corpus(store):
    before = _corpus_fingerprint()
    # Exercise the whole agent-facing read path.
    store.get_document(DOC_ID)
    sp = store.spans(DOC_ID)[0]
    store.get_span(DOC_ID, sp.char_start, sp.char_end)
    retriever = Retriever(store)
    retriever.search("total assets", 5)
    check_support("How much term debt does Apple carry?", retriever)
    assert _corpus_fingerprint() == before, "a read operation mutated the corpus (I4 violated)"


def test_agent_read_classes_expose_no_corpus_mutator(store):
    for cls in (SpanStore, Retriever):
        for forbidden in ("write", "append", "update", "delete", "save"):
            assert not hasattr(cls, forbidden), f"{cls.__name__} exposes {forbidden} (I4)"


def test_audit_log_is_the_only_append_surface():
    assert hasattr(AuditLog, "append")
    assert not hasattr(SpanStore, "append")
    assert not hasattr(Retriever, "append")
