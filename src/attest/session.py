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
from .spans import SpanStore
from .support import SupportResult, check_support
from .verify import VerifyResult, answer_from_json, verify

_PRECISION = 6


def _hits(hits) -> list[dict]:
    return [{"span_id": h.span.span_id, "score": round(h.score, _PRECISION)} for h in hits]


def support_record(query: str, result: SupportResult, kind: str = "check_support") -> dict:
    """Canonical, loggable record of a check_support / check_claim interaction.

    `kind` distinguishes the two (both re-derive from the query the same way), so
    a check_claim entry stays replayable and is not mislabelled as check_support.
    """
    return {
        "kind": kind,
        "query": query,
        "status": result.status,
        "supporting": _hits(result.supporting),
        "closest": _hits(result.closest),
    }


def replay_support(payload: dict, retriever: Retriever) -> dict:
    """Re-derive a check_support / check_claim interaction from the logged query alone."""
    kind = payload.get("kind", "check_support")
    return support_record(payload["query"], check_support(payload["query"], retriever), kind)


def verify_record(answer_json: dict, result: VerifyResult, outcome: str | None = None) -> dict:
    """Loggable record of a verify interaction — self-contained and replayable.

    Stores the answer-with-tags input (so verify can be re-run from the log alone,
    I5/I6) alongside the derived verdict. `outcome` (D16: answer/correction/partial)
    is the agent's self-declared outcome class — metadata for review / the evidence
    view; included only when provided, so existing records are byte-unchanged (I6).
    """
    rec = {
        "kind": "verify",
        "answer": answer_json,
        "ok": result.ok,
        "unbound": result.unbound(),
    }
    if outcome is not None:
        rec["outcome"] = outcome
    return rec


def replay_verify(payload: dict, store: SpanStore) -> dict:
    """Re-run verify from the logged answer alone and re-derive the record (I6)."""
    return verify_record(
        payload["answer"], verify(answer_from_json(payload["answer"]), store),
        payload.get("outcome"),
    )


def replays_identically(payload: dict, engine) -> bool:
    """True iff replaying the record reproduces it byte-identically (I6).

    `engine` is a `Retriever` for support/claim records, a `SpanStore` for verify.
    """
    if payload.get("kind") == "verify":
        return replay_verify(payload, engine) == payload
    return replay_support(payload, engine) == payload
