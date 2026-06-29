"""ATTEST tool registry (ROADMAP M4-T1/M4-T2, brief §5).

The single source of truth for the tools Claude Code calls — shared by both the
MCP server (`mcp_server.py`) and the CLI mirror (`cli.py`), so the two interfaces
can never drift. Each `Tool` is a name + description + a JSON-Schema `input_schema`
+ a pure handler taking a JSON-able args dict and returning a JSON-able dict. The
schema is the tool's contract on the wire — the MCP adapter advertises it verbatim
(M4-T2), so the agent sees the same shape the CLI accepts.

Read/write asymmetry (I4) is structural: only the three write tools
(`check_support` / `check_claim` / `verify`, `read_only=False`) close over the
audit log and append a replayable record (I5); read tools hold no log reference,
so they cannot write even by mistake (M4-T3). Stdlib-only — the MCP dependency
lives in `mcp_server.py`, kept out of the Layer-0 gate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .audit import AuditLog
from .ingest import DocumentStore
from .retrieval import Hit, Retriever
from .session import support_record, verify_record
from .spans import SpanStore
from .support import check_support
from .verify import answer_from_json, result_to_json, verify


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    handler: Callable[[dict], dict]
    read_only: bool = True
    input_schema: dict = field(default_factory=lambda: {"type": "object"})


# --- JSON-Schema fragments (the on-the-wire contract; advertised by the MCP adapter) ---

_ATOM_SCHEMA: dict = {
    "type": "object",
    "description": "A load-bearing atom bound to an exact source location (D9/I1).",
    "properties": {
        "text": {"type": "string", "description": "The literal asserted at the location."},
        "doc_id": {"type": "string"},
        "char_start": {"type": "integer", "minimum": 0},
        "char_end": {"type": "integer", "minimum": 0},
        "content_hash": {
            "type": ["string", "null"],
            "description": "Doc hash the binding was made against (drift check, I3).",
        },
    },
    "required": ["text", "doc_id", "char_start", "char_end"],
    "additionalProperties": False,
}

_ANSWER_SCHEMA: dict = {
    "type": "object",
    "description": "A composed answer: sentences, each with bound atoms + derived values.",
    "properties": {
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "atoms": {"type": "array", "items": _ATOM_SCHEMA},
                    "derived": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "operation": {"type": "string", "enum": [
                                    "subtract", "sum", "multiply", "divide", "ratio",
                                    "percent_change", "gt", "ge", "lt", "le", "eq",
                                    "within_range"]},
                                "operands": {"type": "array", "items": _ATOM_SCHEMA},
                            },
                            "required": ["text", "operation", "operands"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["sentences"],
    "additionalProperties": False,
}


def _obj(properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


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
    # The audit log is the single writable surface (I4); it is the *only* thing the
    # write tools below close over. The read tools never receive it, so the
    # read/write asymmetry is structural — a read handler cannot append even by
    # mistake, because it holds no reference to a log. (M4-T3)
    log = AuditLog(audit_path) if audit_path is not None else None

    def _append(payload: dict) -> None:
        if log is not None:
            log.append(payload)

    tools: list[Tool] = []

    def reg(
        name: str,
        desc: str,
        fn: Callable[[dict], dict],
        schema: dict,
        read_only: bool = True,
    ) -> None:
        tools.append(Tool(name, desc, fn, read_only, schema))

    # --- Read tools: pure, side-effect-free; no log reference (I4) ---

    reg("search_corpus", "Ranked candidate spans for a query (with offsets).",
        lambda a: {"hits": [_hit(h) for h in retriever.search(a["query"], a.get("k", 10))]},
        _obj(
            {
                "query": {"type": "string"},
                "k": {"type": "integer", "minimum": 1, "default": 10},
            },
            ["query"],
        ))

    reg("get_span", "Fetch + hash-verify a span's exact text (I3).",
        lambda a: {"text": span_store.get_span(a["doc_id"], a["start"], a["end"])},
        _obj(
            {
                "doc_id": {"type": "string"},
                "start": {"type": "integer", "minimum": 0},
                "end": {"type": "integer", "minimum": 0},
            },
            ["doc_id", "start", "end"],
        ))

    reg("get_document", "Full hash-verified canonical text — read freely (D11).",
        lambda a: {"doc_id": a["doc_id"], "text": span_store.get_document(a["doc_id"])},
        _obj({"doc_id": {"type": "string"}}, ["doc_id"]))

    # --- Write tools: append a replayable record to the audit log (I5); read_only=False ---

    def _check_support(a: dict) -> dict:
        rec = support_record(a["query"], check_support(a["query"], retriever))
        _append(rec)
        return rec

    def _check_claim(a: dict) -> dict:
        rec = support_record(a["claim"], check_support(a["claim"], retriever), kind="check_claim")
        _append(rec)
        return rec

    def _verify(a: dict) -> dict:
        result = verify(answer_from_json(a["answer"]), span_store)
        _append(verify_record(a["answer"], result, a.get("outcome")))
        return result_to_json(result)

    reg("check_support", "Supporting spans or 'insufficient' — the abstention decision (I2).",
        _check_support, _obj({"query": {"type": "string"}}, ["query"]), read_only=False)

    reg("check_claim", "Resolve a user-supplied claim to supporting spans (or none).",
        _check_claim, _obj({"claim": {"type": "string"}}, ["claim"]), read_only=False)

    reg("verify", "Resolve every bound atom + recompute derivations; flag unbound figures (I1/D9).",
        _verify, _obj({
            "answer": _ANSWER_SCHEMA,
            "outcome": {"type": "string", "enum": ["answer", "correction", "partial"],
                        "description": "Outcome class (D16) — for review; correction = "
                                       "grounded refutation of a false premise."},
        }, ["answer"]), read_only=False)

    if log is not None:

        def _get_audit_log(a: dict) -> dict:
            entries = log.entries()[a.get("offset", 0):]
            return {"entries": [{"seq": e.seq, "payload": e.payload} for e in entries]}

        reg("get_audit_log", "Replay past interactions from the audit log (I5).", _get_audit_log,
            _obj({"offset": {"type": "integer", "minimum": 0, "default": 0}}, []))

    return {t.name: t for t in tools}
