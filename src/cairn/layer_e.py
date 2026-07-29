"""Layer-E scoring — agent end-to-end eval, deterministic half (ROADMAP M2-T6).

Layer-E drives the *real* Claude Code agent over the golden set through the MCP
tools, then scores what it did. The agent is a model, so the run is
non-deterministic and **periodic, not a blocking gate** (brief §3). But the
agent's tool calls are logged immutably (I5), so a large part of the scoring is
*deterministic and replayable from the audit log* — that's what lives here:

  - **decision correctness** — did the present/abstain decision match the item's
    expected outcome class (D16: answer | abstain | correction | partial)? A
    passing `verify` record means it presented; its absence means it abstained.
  - **verify-catch count** — how often `verify` flagged an ungrounded draft.

The remaining Layer-E metrics are model/extra and live in the runner: entailment
(LLM-as-judge over the cited spans), false-premise refutation (did a *correction*
actually refute?), and calibration (Brier). This module stays pure so its scoring
is itself testable in the Layer-0 gate.

A log *segment* is the slice of audit entries produced while the agent worked one
golden item (the runner snapshots the log length between items).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .spans import SpanStore


def ratified_manifest_sha256(items: list[dict], item_ids: list[str]) -> str:
    """Content hash over the *ratified* golden items — the oracle-freeze primitive.

    Canonical JSON of each ratified item (sorted keys, in id order), sha256'd. A
    ratified golden set records this under `ratified.manifest_sha256`; the standing
    freeze test recomputes it. Any edit to — or deletion of — a ratified item
    changes the hash and fails the gate ("the oracle is sacred"). Items whose id is
    NOT in `item_ids` are ignored, so the set stays **append-only**: new items may
    be added freely; the frozen ones cannot be quietly changed. Re-ratifying is the
    only sanctioned path — it needs a new decision + a re-stamped hash.
    """
    by_id = {it["id"]: it for it in items}
    blob = "\n".join(
        json.dumps(by_id[i], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for i in sorted(item_ids) if i in by_id
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

# Five first-class outcomes (D16 + D22). "Ground or abstain" is not binary:
# rejecting a false premise WITH the contradicting evidence is a grounded
# *correction*; answering an in-corpus part while flagging the rest is *partial*;
# and declining a LEGAL conclusion (novelty/validity/infringement/claim
# construction, D10) is a *refusal to adjudicate* — distinct from `abstain`
# because the evidence is often PRESENT; what's declined is the conclusion (UPL
# boundary). Only `abstain` and `refuse` stay silent on the conclusion.
ANSWER, ABSTAIN, CORRECTION, PARTIAL, REFUSE = (
    "answer", "abstain", "correction", "partial", "refuse",
)
PRESENTS = {ANSWER, CORRECTION, PARTIAL}  # classes where the agent SHOULD present

# The corpus a golden item belongs to when it does not name one. Per-item `doc_id`
# wins, so a patent item resolves against the patent store without a code change.
GOLDEN_DOC_ID = "AAPL-10K-FY2024"


def expected_outcome(item: dict) -> str:
    """Derive the expected outcome class from the golden item (no seed edits)."""
    if item.get("answerable"):
        return ANSWER
    beh = item.get("expected_behavior")
    if beh == "reject-false-premise":
        return CORRECTION
    if beh == "partial-abstain":
        return PARTIAL
    if beh == "refuse-to-adjudicate":
        return REFUSE
    return ABSTAIN


@dataclass(frozen=True)
class ItemScore:
    item_id: str
    expected: str              # answer | abstain | correction | partial | refuse
    presented: bool            # a passing verify record exists → the agent presented
    decision_correct: bool     # present/abstain decision matches the expected class
    verify_failures: int       # verify records the agent ran that did NOT pass
    evidence_correct: bool | None = None   # cited the RIGHT span, not merely a real one


def gold_spans(item: dict, store: SpanStore) -> list[tuple[str, int, int]]:
    """The golden item's supporting quotes resolved to offsets (RT-8).

    A SET, not a single span: a figure recurs across a 10-K (the same total appears in
    the balance sheet, the MD&A and a note), so more than one location can be the right
    answer. `resolve_quote` enforces the D7 resolution invariant, so an ambiguous quote
    raises rather than silently binding to the first hit. Unresolvable quotes are
    skipped — an item with none is simply not evidence-scoreable, which is reported
    rather than counted as a pass.
    """
    out = []
    for s in item.get("supporting", []):
        quote = s.get("verbatim_quote")
        if not quote:
            continue
        try:
            start, end = store.resolve_quote(item.get("doc_id", GOLDEN_DOC_ID), quote)
        except Exception:  # noqa: BLE001 — unresolvable gold is reported, not fatal
            continue
        out.append((item.get("doc_id", GOLDEN_DOC_ID), start, end))
    return out


def cited_spans(log_segment: list[dict]) -> list[tuple[str, int, int]]:
    """Every atom location the agent actually bound, from the logged answers."""
    out = []
    for e in log_segment:
        if e.get("kind") != "verify" or not e.get("ok"):
            continue
        for sent in (e.get("answer") or {}).get("sentences", []):
            for a in sent.get("atoms", []):
                if {"doc_id", "char_start", "char_end"} <= a.keys():
                    out.append((a["doc_id"], a["char_start"], a["char_end"]))
            for d in sent.get("derived", []):
                for o in d.get("operands", []):
                    if {"doc_id", "char_start", "char_end"} <= o.keys():
                        out.append((o["doc_id"], o["char_start"], o["char_end"]))
    return out


def _overlaps(a: tuple[str, int, int], b: tuple[str, int, int]) -> bool:
    """Same document and the ranges intersect. Overlap rather than equality: the agent
    may cite a tighter slice ("364,980") than the gold quote ("Total assets $ 364,980
    $ 352,583") or a wider one, and both point at the same evidence."""
    return a[0] == b[0] and a[1] < b[2] and b[1] < a[2]


def score_item(item: dict, log_segment: list[dict],
               store: SpanStore | None = None) -> ItemScore:
    """Score one item. Pass `store` to also grade the EVIDENCE (RT-8).

    Without it this measures only the present/abstain decision — label-only accuracy,
    in FEVER's exact sense, for a system whose entire product claim is span provenance.
    FEVER's published 50.91% -> 31.87% drop when evidence is scored conjunctively is the
    size of what that omission can hide.
    """
    verifies = [e for e in log_segment if e.get("kind") == "verify"]
    presented = any(e.get("ok") for e in verifies)
    expected = expected_outcome(item)

    evidence_correct: bool | None = None
    if store is not None and expected in PRESENTS and presented:
        gold = gold_spans(item, store)
        if gold:                       # no resolvable gold → not scoreable, stays None
            cited = cited_spans(log_segment)
            evidence_correct = any(_overlaps(c, g) for c in cited for g in gold)

    return ItemScore(
        item_id=item["id"],
        expected=expected,
        presented=presented,
        decision_correct=(presented == (expected in PRESENTS)),
        verify_failures=sum(1 for e in verifies if not e.get("ok")),
        evidence_correct=evidence_correct,
    )


def aggregate(scores: list[ItemScore]) -> dict:
    def rate(xs: list[bool]) -> float | None:
        return round(sum(xs) / len(xs), 4) if xs else None

    def of(cls: str) -> list[ItemScore]:
        return [s for s in scores if s.expected == cls]

    return {
        "n": len(scores),
        "by_class": {c: len(of(c)) for c in (ANSWER, ABSTAIN, CORRECTION, PARTIAL, REFUSE)},
        # the present/abstain decision matched the expected class, overall
        "decision_accuracy": rate([s.decision_correct for s in scores]),
        # per class: did it do the right kind of thing?
        "answer_rate": rate([s.presented for s in of(ANSWER)]),
        "abstention_accuracy": rate([not s.presented for s in of(ABSTAIN)]),
        "correction_rate": rate([s.presented for s in of(CORRECTION)]),
        "partial_rate": rate([s.presented for s in of(PARTIAL)]),
        # the patent cardinal rule (D10/D22): declined the legal conclusion?
        "refusal_accuracy": rate([not s.presented for s in of(REFUSE)]),
        "verify_catches": sum(s.verify_failures for s in scores),
        "failures": [s.item_id for s in scores if not s.decision_correct],
        # RT-8: the conjunctive number — did it cite the RIGHT span, not merely a real
        # one — reported ALONGSIDE the decision number, with the gap between them
        # published rather than smoothed. The gap is the honest headline: a decision
        # score that outruns its evidence score is measuring the verdict, not the
        # provenance, and provenance is the whole product claim.
        **_evidence_block(scores),
    }


def _evidence_block(scores: list[ItemScore]) -> dict:
    scored = [s for s in scores if s.evidence_correct is not None]
    if not scored:
        # Never emit a null that reads as 0% or as "clean" — say it wasn't measured.
        return {"evidence_accuracy": None,
                "evidence_note": "not scored (no store passed to score_item)"}
    ev = round(sum(s.evidence_correct for s in scored) / len(scored), 4)
    dec = [s for s in scored if s.decision_correct]
    dec_rate = round(len(dec) / len(scored), 4)
    return {
        "evidence_accuracy": ev,
        "evidence_n": len(scored),
        "evidence_unscoreable": len(scores) - len(scored),
        "decision_minus_evidence": round(dec_rate - ev, 4),
        "evidence_failures": [s.item_id for s in scored if not s.evidence_correct],
    }


# --- entailment judge (the one model-as-judge in the system; isolated here) ---
#
# `verify` confirms a citation is *real*; this judge asks whether the cited span
# actually *supports* the claim (entailment) — the runtime-ungated bit, measured
# offline (brief §3). The model call is injected (`ask`) so the parsing logic is
# deterministic and testable; the live default shells to `claude -p`.


@dataclass(frozen=True)
class Verdict:
    yes: bool   # the asked YES/NO condition holds
    raw: str


def _verdict(raw: str) -> Verdict:
    """Parse a model reply whose first line is YES/NO. Conservative: only explicit YES."""
    first = raw.strip().splitlines()[0].strip().upper() if raw.strip() else ""
    return Verdict(yes=first.startswith("YES"), raw=raw)


_JUDGE_PROMPT = (
    "You are a strict entailment judge for a grounded-retrieval system.\n"
    "Does the SOURCE span, on its own, support the CLAIM? Consider negation, the "
    "wrong period/entity, and attachment. Answer EXACTLY 'YES' or 'NO' on the first "
    "line; default to NO if uncertain.\n\nCLAIM: {claim}\nSOURCE: {span}\n"
)

_REFUTE_PROMPT = (
    "A user's QUESTION contains a FALSE PREMISE. Did the ANSWER reject/correct that "
    "premise (rather than accept it and confabulate)? Answer EXACTLY 'YES' or 'NO' on "
    "the first line; YES only if it clearly refutes the premise.\n\n"
    "QUESTION: {question}\nANSWER: {answer}\n"
)


def judge_entailment(claim: str, span: str, ask: Callable[[str], str]) -> Verdict:
    """Ask the injected model whether `span` supports `claim` (only explicit YES counts)."""
    return _verdict(ask(_JUDGE_PROMPT.format(claim=claim, span=span)))


def judge_refutes_premise(question: str, answer: str, ask: Callable[[str], str]) -> Verdict:
    """For a false-premise item: did the answer refute the premise (a grounded correction)?"""
    return _verdict(ask(_REFUTE_PROMPT.format(question=question, answer=answer)))


def claude_ask(prompt: str, timeout: int = 120) -> str:  # pragma: no cover - billed model call
    """Default judge backend: a plain (no-MCP) headless Claude Code call. `--bare`
    forces ANTHROPIC_API_KEY auth (never keychain/OAuth), matching the eval env."""
    import subprocess

    return subprocess.run(  # noqa: S603
        ["claude", "-p", prompt, "--bare"], capture_output=True, text=True,  # noqa: S607
        stdin=subprocess.DEVNULL, timeout=timeout
    ).stdout


def claims_and_spans(verify_payload: dict, get_span: Callable[[str, int, int], str]) -> Iterator:
    """From a logged `verify` record, yield (claim_sentence, [cited span texts]) for the judge."""
    for sent in verify_payload.get("answer", {}).get("sentences", []):
        spans = [
            get_span(a["doc_id"], a["char_start"], a["char_end"]) for a in sent.get("atoms", [])
        ]
        if spans:
            yield sent["text"], spans


# --- abstention calibration (pure: Brier + reliability over (confidence, correct)) ---


def brier_score(pairs: list[tuple[float, bool]]) -> float | None:
    """Mean squared error of stated confidence vs outcome. 0 = perfect, 1 = worst."""
    if not pairs:
        return None
    return round(sum((c - (1.0 if ok else 0.0)) ** 2 for c, ok in pairs) / len(pairs), 4)


def reliability(pairs: list[tuple[float, bool]], bins: int = 5) -> list[dict]:
    """Per confidence bucket: count, mean stated confidence, observed accuracy."""
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [(c, ok) for c, ok in pairs if (lo <= c < hi or (b == bins - 1 and c == 1.0))]
        if not bucket:
            continue
        out.append({
            "bucket": f"{lo:.1f}-{hi:.1f}",
            "n": len(bucket),
            "mean_confidence": round(sum(c for c, _ in bucket) / len(bucket), 4),
            "accuracy": round(sum(1 for _, ok in bucket if ok) / len(bucket), 4),
        })
    return out
