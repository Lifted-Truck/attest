"""Standing boundary test — read/write asymmetry at the tool surface (ROADMAP M4-T3; I4/I5).

The agent reaches the corpus only through the registry. Here we pin the asymmetry
at that boundary: the read tools (`search_corpus` / `get_span` / `get_document` /
`get_audit_log`) have **zero side effects**, and only the three write tools
(`check_support` / `check_claim` / `verify`) append to the audit log — which is the
sole writable surface (I4). Every append is a replayable record (I5/I6).
"""

import hashlib
from pathlib import Path

import pytest

from attest.audit import AuditLog
from attest.session import replays_identically
from attest.spans import SpanStore
from attest.tools import default_registry

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "corpus" / "store"
DOC_ID = "AAPL-10K-FY2024"

READ_TOOLS = {"search_corpus", "get_span", "get_document", "get_audit_log"}
WRITE_TOOLS = {"check_support", "check_claim", "verify"}


def _ta_span(registry) -> tuple[int, int]:
    """The 'Total assets' line offsets, derived at runtime (robust to re-normalization)."""
    hits = registry["search_corpus"].handler({"query": "total assets", "k": 8})["hits"]
    h = next(x for x in hits if x["text"].startswith("Total assets $"))
    return h["char_start"], h["char_end"]


@pytest.fixture
def registry(tmp_path):
    if not (STORE / DOC_ID).exists():
        pytest.skip("corpus not ingested — run scripts/ingest_corpus.py")
    return default_registry(STORE, audit_path=tmp_path / "audit.jsonl")


def _read_call(registry, name):
    """Exercise one read tool with valid args."""
    start, end = _ta_span(registry)
    args = {
        "search_corpus": {"query": "total assets", "k": 3},
        "get_span": {"doc_id": DOC_ID, "start": start, "end": end},
        "get_document": {"doc_id": DOC_ID},
        "get_audit_log": {},
    }[name]
    return registry[name].handler(args)


def _write_call(registry, name):
    """Exercise one write tool with valid args."""
    start, end = _ta_span(registry)
    text = registry["get_span"].handler({"doc_id": DOC_ID, "start": start, "end": end})["text"]
    off = start + text.index("364,980")
    atom = {"text": "364,980", "doc_id": DOC_ID, "char_start": off, "char_end": off + 7}
    args = {
        "check_support": {"query": "How much term debt does Apple carry?"},
        "check_claim": {"claim": "Apple's total assets were $364,980 million."},
        "verify": {
            "answer": {
                "sentences": [
                    {"text": "Apple's total assets were $364,980 million.", "atoms": [atom]}
                ]
            }
        },
    }[name]
    return registry[name].handler(args)


def test_read_only_flags_match_intent(registry):
    """The `read_only` flag is the declared contract; pin it for both classes."""
    for name in READ_TOOLS:
        assert registry[name].read_only is True, f"{name} should be read-only"
    for name in WRITE_TOOLS:
        assert registry[name].read_only is False, f"{name} writes the log"


def test_read_tools_have_zero_side_effects(registry, tmp_path):
    """Reads mutate neither the audit log nor the corpus."""
    audit_path = tmp_path / "audit.jsonl"
    log = AuditLog(audit_path)
    log.append({"kind": "check_support", "query": "seed", "status": "supported"})
    seeded = audit_path.read_bytes()
    corpus_before = _corpus_fingerprint()

    for name in READ_TOOLS:
        _read_call(registry, name)

    assert audit_path.read_bytes() == seeded, "a read tool wrote to the audit log (I4)"
    assert _corpus_fingerprint() == corpus_before, "a read tool mutated the corpus (I4)"


def test_only_write_tools_append_exactly_one_entry(registry, tmp_path):
    """Each write tool appends exactly one entry; reads append none."""
    log = AuditLog(tmp_path / "audit.jsonl")

    for name in sorted(READ_TOOLS):
        before = len(log.entries())
        _read_call(registry, name)
        assert len(log.entries()) == before, f"read tool {name} appended to the log"

    for name in sorted(WRITE_TOOLS):
        before = len(log.entries())
        _write_call(registry, name)
        assert len(log.entries()) == before + 1, f"{name} did not append exactly one entry"

    log.verify_chain()  # the chain still verifies after all appends (I5)


def test_appended_records_are_replayable(registry, tmp_path):
    """Every write tool's entry re-derives byte-identically from the log alone (I5/I6)."""
    from attest.ingest import DocumentStore
    from attest.retrieval import Retriever

    store = SpanStore.from_store(DocumentStore(STORE))
    retriever = Retriever(store)
    log = AuditLog(tmp_path / "audit.jsonl")

    for name in WRITE_TOOLS:
        _write_call(registry, name)

    for entry in log.entries():
        engine = store if entry.payload["kind"] == "verify" else retriever
        assert replays_identically(entry.payload, engine), f"{entry.payload['kind']} not replayable"


def test_no_log_configured_means_writes_are_silent_noops():
    """With no audit path, write tools still answer but append nowhere (degraded I5)."""
    if not (STORE / DOC_ID).exists():
        pytest.skip("corpus not ingested")
    reg = default_registry(STORE, audit_path=None)
    assert "get_audit_log" not in reg
    out = reg["check_support"].handler({"query": "How much term debt does Apple carry?"})
    assert out["status"] == "supported"  # functional, just unlogged


def _corpus_fingerprint() -> dict[str, str]:
    return {
        str(p.relative_to(STORE)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(STORE.rglob("*")) if p.is_file()
    }
