"""Standing tests for the tool registry + CLI mirror (ROADMAP M4-T1).

Tools are enumerated, and the CLI invokes the *same* registry functions (so the
MCP and CLI interfaces can't drift). The MCP adapter is tested only when the
optional `mcp` SDK is present, keeping the gate dependency-free.
"""

import json
from pathlib import Path

import pytest

from attest.audit import AuditLog
from attest.cli import main as cli_main
from attest.tools import default_registry

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "corpus" / "store"
DOC_ID = "AAPL-10K-FY2024"


@pytest.fixture(scope="module")
def registry():
    if not (STORE / DOC_ID).exists():
        pytest.skip("corpus not ingested — run scripts/ingest_corpus.py")
    return default_registry(STORE, audit_path=None)


def _ta_span(registry) -> tuple[int, int]:
    """Locate the 'Total assets' line's offsets at runtime (robust to re-normalization)."""
    hits = registry["search_corpus"].handler({"query": "total assets", "k": 8})["hits"]
    h = next(x for x in hits if x["text"].startswith("Total assets $"))
    return h["char_start"], h["char_end"]


def _bind_total_assets(registry, literal: str = "364,980") -> dict:
    """JSON atom binding a figure to its exact offset on the 'Total assets' line."""
    start, end = _ta_span(registry)
    text = registry["get_span"].handler({"doc_id": DOC_ID, "start": start, "end": end})["text"]
    off = start + text.index(literal)
    return {"text": literal, "doc_id": DOC_ID, "char_start": off, "char_end": off + len(literal)}


def test_expected_tools_are_enumerated(registry):
    assert {
        "search_corpus", "get_span", "get_document", "check_support", "check_claim", "verify"
    } <= set(registry)


def test_every_tool_advertises_an_object_schema(registry):
    """The on-the-wire contract: each tool carries a JSON-Schema the MCP adapter serves."""
    for tool in registry.values():
        assert tool.input_schema["type"] == "object"
        assert "properties" in tool.input_schema


# --- M4-T2 contract tests: verify / check_claim / get_audit_log ---


def test_verify_flags_an_unbound_claim(registry):
    """(a) A figure asserted with no binding cannot pass verify through the tool."""
    answer = {"sentences": [{"text": "Apple's total assets were $999,999 million.", "atoms": []}]}
    out = registry["verify"].handler({"answer": answer})
    assert out["ok"] is False
    assert "999,999" in out["unbound"]


def test_verify_passes_a_bound_claim(registry):
    """A real binding round-trips JSON → Answer → verify and resolves ok (I1/I3)."""
    answer = {
        "sentences": [
            {
                "text": "Apple's total assets were $364,980 million.",
                "atoms": [_bind_total_assets(registry)],
            }
        ]
    }
    out = registry["verify"].handler({"answer": answer})
    assert out["ok"] is True
    assert out["sentences"][0]["atoms"][0]["status"] == "ok"
    assert not out["unbound"]


def test_check_claim_resolves_to_spans_or_empty(registry):
    """(b) A backed claim returns supporting spans; an unbacked one returns none."""
    backed = registry["check_claim"].handler(
        {"claim": "Apple's total assets were $364,980 million."}
    )
    assert backed["status"] == "supported" and backed["supporting"]

    unbacked = registry["check_claim"].handler({"claim": "Apple's customer churn rate is 4%."})
    assert unbacked["status"] == "insufficient" and unbacked["supporting"] == []


def test_get_audit_log_replays_without_side_effects(tmp_path):
    """(c) Reading the log returns the entries and mutates nothing (I4/I5)."""
    if not (STORE / DOC_ID).exists():
        pytest.skip("corpus not ingested")
    audit_path = tmp_path / "audit.jsonl"
    log = AuditLog(audit_path)
    log.append({"kind": "check_support", "query": "total assets", "status": "supported"})
    log.append({"kind": "verify", "ok": True})

    before = audit_path.read_bytes()
    registry = default_registry(STORE, audit_path)

    first = registry["get_audit_log"].handler({})
    assert [e["seq"] for e in first["entries"]] == [0, 1]
    assert first["entries"][0]["payload"]["query"] == "total assets"

    # No side effects: the bytes are untouched, the chain still verifies, and a
    # second read is byte-identical to the first (pure replay).
    assert audit_path.read_bytes() == before
    log.verify_chain()
    assert registry["get_audit_log"].handler({}) == first

    # offset is honoured (replay a suffix of the log).
    assert [e["seq"] for e in registry["get_audit_log"].handler({"offset": 1})["entries"]] == [1]


def test_search_corpus_returns_offsets(registry):
    hits = registry["search_corpus"].handler({"query": "total assets", "k": 5})["hits"]
    assert hits and all({"doc_id", "char_start", "char_end", "score"} <= set(h) for h in hits)


def test_get_span_round_trips(registry):
    start, end = _ta_span(registry)
    out = registry["get_span"].handler({"doc_id": DOC_ID, "start": start, "end": end})
    assert "364,980" in out["text"]


def test_check_support_decides(registry):
    answered = registry["check_support"].handler({"query": "How much term debt does Apple carry?"})
    assert answered["status"] == "supported" and answered["supporting"]
    absent = registry["check_support"].handler({"query": "Apple's customer churn rate?"})
    assert absent["status"] == "insufficient"


def test_get_audit_log_registered_only_with_a_path(tmp_path):
    if not (STORE / DOC_ID).exists():
        pytest.skip("corpus not ingested")
    assert "get_audit_log" not in default_registry(STORE, None)
    assert "get_audit_log" in default_registry(STORE, tmp_path / "audit.jsonl")


def test_cli_list_and_call(registry, capsys):
    if not (STORE / DOC_ID).exists():
        pytest.skip("corpus not ingested")
    assert cli_main(["--store", str(STORE), "list"]) == 0
    listed = capsys.readouterr().out
    assert "search_corpus" in listed and "get_span" in listed

    args = json.dumps({"query": "total assets", "k": 3})
    assert cli_main(["--store", str(STORE), "call", "search_corpus", args]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hits"]


def test_cli_unknown_tool_errors(registry, capsys):
    if not (STORE / DOC_ID).exists():
        pytest.skip("corpus not ingested")
    assert cli_main(["--store", str(STORE), "call", "no_such_tool"]) == 2


def test_mcp_adapter_builds_when_sdk_present():
    pytest.importorskip("mcp")  # optional dependency; skipped if not installed
    if not (STORE / DOC_ID).exists():
        pytest.skip("corpus not ingested")
    from attest.mcp_server import build_server
    server = build_server(STORE)
    assert server is not None


def test_support_threshold_is_configurable(registry):
    """A lower per-engagement floor flips a borderline query from insufficient → supported.

    The EDGAR floor (15.0) is calibrated for EDGAR; a different corpus (e.g. patents,
    whose BM25 scores run lower) sets its own via ATTEST_SUPPORT_THRESHOLD (D12)."""
    q = "What is Apple's customer churn rate?"
    assert registry["check_support"].handler({"query": q})["status"] == "insufficient"
    loose = default_registry(STORE, None, support_threshold=5.0)
    assert loose["check_support"].handler({"query": q})["status"] == "supported"
