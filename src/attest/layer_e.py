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


def score_item(item: dict, log_segment: list[dict]) -> ItemScore:
    verifies = [e for e in log_segment if e.get("kind") == "verify"]
    presented = any(e.get("ok") for e in verifies)
    expected = expected_outcome(item)
    return ItemScore(
        item_id=item["id"],
        expected=expected,
        presented=presented,
        decision_correct=(presented == (expected in PRESENTS)),
        verify_failures=sum(1 for e in verifies if not e.get("ok")),
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
