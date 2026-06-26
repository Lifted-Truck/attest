"""Standing tests for the tool registry + CLI mirror (ROADMAP M4-T1).

Tools are enumerated, and the CLI invokes the *same* registry functions (so the
MCP and CLI interfaces can't drift). The MCP adapter is tested only when the
optional `mcp` SDK is present, keeping the gate dependency-free.
"""

import json
from pathlib import Path

import pytest

from attest.cli import main as cli_main
from attest.tools import default_registry

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "corpus" / "store"
DOC_ID = "AAPL-10K-FY2024"
TOTAL_ASSETS_SPAN = (139998, 140030)  # the "Total assets ..." line offsets


@pytest.fixture(scope="module")
def registry():
    if not (STORE / DOC_ID).exists():
        pytest.skip("corpus not ingested — run scripts/ingest_corpus.py")
    return default_registry(STORE, audit_path=None)


def test_expected_tools_are_enumerated(registry):
    assert {"search_corpus", "get_span", "get_document", "check_support", "check_claim"} <= set(
        registry
    )


def test_search_corpus_returns_offsets(registry):
    hits = registry["search_corpus"].handler({"query": "total assets", "k": 5})["hits"]
    assert hits and all({"doc_id", "char_start", "char_end", "score"} <= set(h) for h in hits)


def test_get_span_round_trips(registry):
    start, end = TOTAL_ASSETS_SPAN
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
