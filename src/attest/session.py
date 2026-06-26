"""Interaction records + replay (ROADMAP M3-T2; I5, I6).

Bridges the deterministic tools and the audit log: turn a tool result into a
canonical, loggable record, and **replay** it — re-derive the evidence path from
the logged query alone and confirm it reproduces byte-identically (I6). That is
what makes the log an audit trail and not just a diary: any past interaction can
be reconstructed and re-checked from the record.

Scores are rounded to a fixed precision so the canonical record is stable across
environments; the underlying retrieval is already deterministic.
"""

from __future__ import annotations

from .retrieval import Retriever
from .support import SupportResult, check_support

_PRECISION = 6


def _hits(hits) -> list[dict]:
    return [{"span_id": h.span.span_id, "score": round(h.score, _PRECISION)} for h in hits]


def support_record(query: str, result: SupportResult) -> dict:
    """Canonical, loggable record of a check_support interaction."""
    return {
        "kind": "check_support",
        "query": query,
        "status": result.status,
        "supporting": _hits(result.supporting),
        "closest": _hits(result.closest),
    }


def replay_support(payload: dict, retriever: Retriever) -> dict:
    """Re-derive a check_support interaction from the logged query alone."""
    return support_record(payload["query"], check_support(payload["query"], retriever))


def replays_identically(payload: dict, retriever: Retriever) -> bool:
    """True iff replaying the record reproduces it byte-identically (I6)."""
    return replay_support(payload, retriever) == payload
