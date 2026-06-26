"""ATTEST tool registry (ROADMAP M4-T1, brief §5).

The single source of truth for the tools Claude Code calls — shared by both the
MCP server (`mcp_server.py`) and the CLI mirror (`cli.py`), so the two interfaces
can never drift. Each `Tool` is a name + description + a pure handler taking a
JSON-able args dict and returning a JSON-able dict.

Read/write asymmetry (I4) is declared per tool (`read_only`) and enforced at the
boundary in M4-T3. Full per-tool contracts + tests land in M4-T2; `verify` (which
takes a structured answer) and the log side-effects are wired then. Stdlib-only —
the MCP dependency lives in `mcp_server.py`, kept out of the Layer-0 gate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .audit import AuditLog
from .ingest import DocumentStore
from .retrieval import Hit, Retriever
from .session import support_record
from .spans import SpanStore
from .support import check_support


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    handler: Callable[[dict], dict]
    read_only: bool = True


def _hit(h: Hit) -> dict:
    s = h.span
    return {
        "doc_id": s.doc_id,
        "span_id": s.span_id,
        "char_start": s.char_start,
        "char_end": s.char_end,
        "score": round(h.score, 6),
        "text": s.text,
    }


def default_registry(
    store_dir: Path | str, audit_path: Path | str | None = None
) -> dict[str, Tool]:
    span_store = SpanStore.from_store(DocumentStore(store_dir))
    retriever = Retriever(span_store)
    tools: list[Tool] = []

    def reg(name: str, desc: str, fn: Callable[[dict], dict], read_only: bool = True) -> None:
        tools.append(Tool(name, desc, fn, read_only))

    reg("search_corpus", "Ranked candidate spans for a query (with offsets).",
        lambda a: {"hits": [_hit(h) for h in retriever.search(a["query"], a.get("k", 10))]})

    reg("get_span", "Fetch + hash-verify a span's exact text (I3).",
        lambda a: {"text": span_store.get_span(a["doc_id"], a["start"], a["end"])})

    reg("get_document", "Full hash-verified canonical text — read freely (D11).",
        lambda a: {"doc_id": a["doc_id"], "text": span_store.get_document(a["doc_id"])})

    reg("check_support", "Supporting spans or 'insufficient' — the abstention decision (I2).",
        lambda a: support_record(a["query"], check_support(a["query"], retriever)))

    reg("check_claim", "Resolve a user-supplied claim to supporting spans (or none).",
        lambda a: support_record(a["claim"], check_support(a["claim"], retriever)))

    if audit_path is not None:
        log = AuditLog(audit_path)

        def _get_audit_log(a: dict) -> dict:
            entries = log.entries()[a.get("offset", 0):]
            return {"entries": [{"seq": e.seq, "payload": e.payload} for e in entries]}

        reg("get_audit_log", "Replay past interactions from the audit log (I5).", _get_audit_log)

    # M4-T2 will add: verify(answer_with_tags) (needs structured input) + the
    # append-to-log side effects on check_support / check_claim / verify (M4-T3).
    return {t.name: t for t in tools}
