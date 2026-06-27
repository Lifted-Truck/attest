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

from collections.abc import Callable, Iterator
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


# --- entailment judge (the one model-as-judge in the system; isolated here) ---
#
# `verify` confirms a citation is *real*; this judge asks whether the cited span
# actually *supports* the claim (entailment) — the runtime-ungated bit, measured
# offline (brief §3). The model call is injected (`ask`) so the parsing logic is
# deterministic and testable; the live default shells to `claude -p`.


@dataclass(frozen=True)
class Verdict:
    entails: bool
    raw: str


_JUDGE_PROMPT = (
    "You are a strict entailment judge for a grounded-retrieval system.\n"
    "Does the SOURCE span, on its own, support the CLAIM? Consider negation, the "
    "wrong period/entity, and attachment. Answer EXACTLY 'YES' or 'NO' on the first "
    "line; default to NO if uncertain.\n\nCLAIM: {claim}\nSOURCE: {span}\n"
)


def judge_entailment(claim: str, span: str, ask: Callable[[str], str]) -> Verdict:
    """Ask the injected model whether `span` supports `claim`. Conservative: only an
    explicit YES counts as entailment."""
    raw = ask(_JUDGE_PROMPT.format(claim=claim, span=span))
    first = raw.strip().splitlines()[0].strip().upper() if raw.strip() else ""
    return Verdict(entails=first.startswith("YES"), raw=raw)


def claude_ask(prompt: str, timeout: int = 120) -> str:  # pragma: no cover - billed model call
    """Default judge backend: a plain (no-MCP) headless Claude Code call."""
    import subprocess

    return subprocess.run(  # noqa: S603
        ["claude", "-p", prompt], capture_output=True, text=True, timeout=timeout  # noqa: S607
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
