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

from .contract import CONTRACT_VERSION
from .retrieval import Retriever
from .spans import SpanStore
from .support import THRESHOLD, SupportResult, check_support
from .verify import OPS_VERSION, VerifyResult, answer_from_json, verify

_PRECISION = 6


def _hits(hits) -> list[dict]:
    return [{"span_id": h.span.span_id, "score": round(h.score, _PRECISION)} for h in hits]


def support_record(
    query: str, result: SupportResult, kind: str = "check_support", *,
    threshold: float = THRESHOLD, retrieval: str = "bm25",
) -> dict:
    """Canonical, loggable record of a check_support / check_claim interaction.

    `kind` distinguishes the two (both re-derive from the query the same way), so
    a check_claim entry stays replayable and is not mislabelled as check_support.
    The `provenance` block (TC-2) stamps the rigor this record was produced under —
    the contract version, the retrieval method, and the support floor used — so it
    stays interpretable after an upgrade and replays deterministically (I6).
    """
    return {
        "kind": kind,
        "query": query,
        "status": result.status,
        "supporting": _hits(result.supporting),
        "closest": _hits(result.closest),
        "provenance": {
            "contract": CONTRACT_VERSION, "retrieval": retrieval, "threshold": threshold,
        },
    }


def replay_support(payload: dict, retriever: Retriever) -> dict:
    """Re-derive a check_support / check_claim interaction from the logged query alone.

    Uses the floor recorded in `provenance` (not the default), so a record made under
    a per-engagement threshold reproduces byte-identically (I6). The provenance stamp
    describes the *original* production context, so replay preserves it verbatim
    (D21/TC-2): a record made under an earlier contract version — or before stamping
    existed — still replays byte-identically after an upgrade."""
    kind = payload.get("kind", "check_support")
    prov = payload.get("provenance", {})
    threshold = prov.get("threshold", THRESHOLD)
    result = check_support(payload["query"], retriever, threshold=threshold)
    rec = support_record(payload["query"], result, kind,
                         threshold=threshold, retrieval=retriever.method)
    if "provenance" in payload:
        rec["provenance"] = payload["provenance"]
    else:                                   # pre-provenance record stays pre-provenance
        rec.pop("provenance")
    return rec


def verify_record(answer_json: dict, result: VerifyResult, outcome: str | None = None,
                  frame_json: dict | None = None, coverage_json: dict | None = None) -> dict:
    """Loggable record of a verify interaction — self-contained and replayable.

    Stores the answer-with-tags input (so verify can be re-run from the log alone,
    I5/I6) alongside the derived verdict. `outcome` (D16/D22) is the agent's
    self-declared outcome class; `frame_json`/`coverage_json` are the agent's
    question frame and its deterministic coverage verdict (M2-T8/D13) — coverage is
    re-derivable from frame + answer, so the record stays replayable. All optional
    fields are included only when provided (existing records byte-unchanged, I6).
    """
    rec = {
        "kind": "verify",
        "answer": answer_json,
        "ok": result.ok,
        "unbound": result.unbound(),
        "provenance": {"contract": CONTRACT_VERSION, "verify_ops": OPS_VERSION},
    }
    if outcome is not None:
        rec["outcome"] = outcome
    if frame_json is not None:
        rec["frame"] = frame_json
        rec["coverage"] = coverage_json
    return rec


def replay_verify(payload: dict, store: SpanStore) -> dict:
    """Re-run verify from the logged answer alone and re-derive the record (I6).

    The verdict (`ok`/`unbound`) — and, when a frame was logged, the coverage
    verdict — are re-derived by the *current* engine; the provenance stamp
    describes the original production context and is preserved verbatim, so
    older-contract and pre-provenance records replay byte-identically (D21/TC-2)
    — while any real behavioral drift still fails on the re-derived fields."""
    from .frame import coverage_for_answer, coverage_to_json, frame_from_json

    answer = answer_from_json(payload["answer"])
    frame_json = payload.get("frame")
    coverage_json = (
        coverage_to_json(coverage_for_answer(frame_from_json(frame_json), answer, store))
        if frame_json is not None else None
    )
    rec = verify_record(
        payload["answer"], verify(answer, store), payload.get("outcome"),
        frame_json, coverage_json,
    )
    if "provenance" in payload:
        rec["provenance"] = payload["provenance"]
    else:
        rec.pop("provenance")
    return rec


def replays_identically(payload: dict, engine) -> bool:
    """True iff replaying the record reproduces it byte-identically (I6).

    `engine` is a `Retriever` for support/claim records, a `SpanStore` for verify.
    """
    if payload.get("kind") == "verify":
        return replay_verify(payload, engine) == payload
    return replay_support(payload, engine) == payload
