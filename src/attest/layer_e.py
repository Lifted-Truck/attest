"""Layer-E scoring — agent end-to-end eval, deterministic half (ROADMAP M2-T6).

Layer-E drives the *real* Claude Code agent over the golden set through the MCP
tools, then scores what it did. The agent is a model, so the run is
non-deterministic and **periodic, not a blocking gate** (brief §3). But the
agent's tool calls are logged immutably (I5), so a large part of the scoring is
*deterministic and replayable from the audit log* — that's what lives here:

  - **abstention correctness** — did the agent abstain on unanswerable items and
    present on answerable ones? Inferred from the log: a passing `verify` record
    means it presented a grounded answer; its absence means it abstained.
  - **verify-catch count** — how often `verify` flagged an ungrounded draft.

The remaining Layer-E metrics are model/extra and live in the runner: entailment
(LLM-as-judge over the cited spans) and abstention calibration (Brier). This
module stays pure so its scoring is itself testable in the Layer-0 gate.

A log *segment* is the slice of audit entries produced while the agent worked one
golden item (the runner snapshots the log length between items).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ItemScore:
    item_id: str
    answerable: bool
    presented: bool            # a passing verify record exists → the agent presented
    abstention_correct: bool   # presented iff answerable
    verify_failures: int       # verify records the agent ran that did NOT pass


def score_item(item: dict, log_segment: list[dict]) -> ItemScore:
    verifies = [e for e in log_segment if e.get("kind") == "verify"]
    presented = any(e.get("ok") for e in verifies)
    answerable = bool(item["answerable"])
    return ItemScore(
        item_id=item["id"],
        answerable=answerable,
        presented=presented,
        abstention_correct=(presented == answerable),
        verify_failures=sum(1 for e in verifies if not e.get("ok")),
    )


def aggregate(scores: list[ItemScore]) -> dict:
    answerable = [s for s in scores if s.answerable]
    unanswerable = [s for s in scores if not s.answerable]

    def rate(xs: list[bool]) -> float | None:
        return round(sum(xs) / len(xs), 4) if xs else None

    return {
        "n": len(scores),
        "n_answerable": len(answerable),
        "n_unanswerable": len(unanswerable),
        # the headline: did it abstain on every unanswerable item?
        "abstention_accuracy": rate([s.presented is False for s in unanswerable]),
        # did it present a grounded answer on answerable items?
        "answer_rate": rate([s.presented for s in answerable]),
        "abstention_correct_overall": rate([s.abstention_correct for s in scores]),
        "verify_catches": sum(s.verify_failures for s in scores),
        "failures": [s.item_id for s in scores if not s.abstention_correct],
    }
