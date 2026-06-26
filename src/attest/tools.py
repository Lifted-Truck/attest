"""ATTEST tool registry (ROADMAP M4-T1/M4-T2, brief §5).

The single source of truth for the tools Claude Code calls — shared by both the
MCP server (`mcp_server.py`) and the CLI mirror (`cli.py`), so the two interfaces
can never drift. Each `Tool` is a name + description + a JSON-Schema `input_schema`
+ a pure handler taking a JSON-able args dict and returning a JSON-able dict. The
schema is the tool's contract on the wire — the MCP adapter advertises it verbatim
(M4-T2), so the agent sees the same shape the CLI accepts.

Read/write asymmetry (I4) is declared per tool (`read_only`) and enforced at the
boundary in M4-T3, which also wires the log side-effects on `check_support` /
`check_claim` / `verify`. Stdlib-only — the MCP dependency lives in
`mcp_server.py`, kept out of the Layer-0 gate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .audit import AuditLog
from .ingest import DocumentStore
from .retrieval import Hit, Retriever
from .session import support_record
from .spans import SpanStore
from .support import check_support
from .verify import (
    Answer,
    AtomBinding,
    DerivedAtom,
    Sentence,
    VerifyResult,
    verify,
)


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
                                "operation": {"type": "string", "enum": ["subtract", "sum"]},
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


# --- verify: JSON args <-> the structured Answer model, and the result back to JSON ---

def _atom_from(d: dict) -> AtomBinding:
    return AtomBinding(
        text=d["text"],
        doc_id=d["doc_id"],
        char_start=d["char_start"],
        char_end=d["char_end"],
        content_hash=d.get("content_hash"),
    )


def _answer_from(a: dict) -> Answer:
    sentences: list[Sentence] = []
    for s in a["sentences"]:
        atoms = [_atom_from(x) for x in s.get("atoms", [])]
        derived = [
            DerivedAtom(
                text=d["text"],
                operation=d["operation"],
                operands=[_atom_from(o) for o in d["operands"]],
            )
            for d in s.get("derived", [])
        ]
        sentences.append(Sentence(text=s["text"], atoms=atoms, derived=derived))
    return Answer(sentences)


def _verify_result(r: VerifyResult) -> dict:
    return {
        "ok": r.ok,
        "unbound": r.unbound(),
        "sentences": [
            {
                "text": s.text,
                "ok": s.ok,
                "unbound_figures": s.unbound_figures,
                "atoms": [
                    {
                        "text": v.binding.text,
                        "doc_id": v.binding.doc_id,
                        "char_start": v.binding.char_start,
                        "char_end": v.binding.char_end,
                        "status": v.status,
                        "found": v.found,
                    }
                    for v in s.atom_verdicts
                ],
                "derived_ok": s.derived_ok,
            }
            for s in r.sentences
        ],
    }


def default_registry(
    store_dir: Path | str, audit_path: Path | str | None = None
) -> dict[str, Tool]:
    span_store = SpanStore.from_store(DocumentStore(store_dir))
    retriever = Retriever(span_store)
    tools: list[Tool] = []

    def reg(
        name: str,
        desc: str,
        fn: Callable[[dict], dict],
        schema: dict,
        read_only: bool = True,
    ) -> None:
        tools.append(Tool(name, desc, fn, read_only, schema))

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

    reg("check_support", "Supporting spans or 'insufficient' — the abstention decision (I2).",
        lambda a: support_record(a["query"], check_support(a["query"], retriever)),
        _obj({"query": {"type": "string"}}, ["query"]))

    reg("check_claim", "Resolve a user-supplied claim to supporting spans (or none).",
        lambda a: support_record(a["claim"], check_support(a["claim"], retriever)),
        _obj({"claim": {"type": "string"}}, ["claim"]))

    reg("verify", "Resolve every bound atom + recompute derivations; flag unbound figures (I1/D9).",
        lambda a: _verify_result(verify(_answer_from(a["answer"]), span_store)),
        _obj({"answer": _ANSWER_SCHEMA}, ["answer"]))

    if audit_path is not None:
        log = AuditLog(audit_path)

        def _get_audit_log(a: dict) -> dict:
            entries = log.entries()[a.get("offset", 0):]
            return {"entries": [{"seq": e.seq, "payload": e.payload} for e in entries]}

        reg("get_audit_log", "Replay past interactions from the audit log (I5).", _get_audit_log,
            _obj({"offset": {"type": "integer", "minimum": 0, "default": 0}}, []))

    # M4-T3 wires the append-to-log side effects on check_support / check_claim /
    # verify and enforces read/write asymmetry (I4) at the MCP boundary.
    return {t.name: t for t in tools}
