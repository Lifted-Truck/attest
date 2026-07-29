"""check_support — the deterministic abstention trigger (ROADMAP M2-T2, D12; I2).

Runs retrieval and applies a relevance floor. If at least one span clears the
floor, returns those spans (ranked, plural — the candidate support). If none do,
returns `insufficient` plus the closest spans found, so the agent can abstain
*and show it looked, and where*.

Scope (D12): this is the **content-absence** half of abstention — provably
deterministic. It does **not** catch semantic traps that retrieve real but
wrong-for-the-question content (wrong period, wrong entity, false premise); those
are the agent's reasoning (D11), measured at Layer-E. `THRESHOLD` is a per-corpus
calibration (separates the golden set's content-absent items ≤~11 from answerable
gold spans ≥~19); the patent corpus recalibrates.
"""

from __future__ import annotations

from dataclasses import dataclass

from .retrieval import Hit, Retriever

THRESHOLD = 15.0
SUPPORTED = "supported"
INSUFFICIENT = "insufficient"


@dataclass
class SupportResult:
    status: str          # "supported" | "insufficient"
    supporting: list[Hit]  # spans clearing the floor, ranked (plural)
    closest: list[Hit]     # when insufficient: nearest spans found (show we looked)

    @property
    def insufficient(self) -> bool:
        return self.status == INSUFFICIENT


def check_support(
    question: str,
    retriever: Retriever,
    *,
    k: int = 20,
    threshold: float = THRESHOLD,
) -> SupportResult:
    hits = retriever.search(question, k)
    clearing = [h for h in hits if h.score >= threshold]
    if clearing:
        return SupportResult(SUPPORTED, clearing, [])
    return SupportResult(INSUFFICIENT, [], hits[:3])


# --- threshold calibration (D20) -------------------------------------------------
# The floor is *fitted from labels*, not hand-tuned: it separates answerable golden
# queries (their top span should clear) from CONTENT-ABSENT ones (should not). The
# semantic traps are deliberately excluded — they retrieve real, high-scoring
# content and are abstained by reasoning (D12), so forcing the floor above them
# would be wrong. Deterministic; the result is meant to be recorded per corpus.
ABSENT_TAGS = ("out-of-document-fact", "not-disclosed-metric")


@dataclass
class Calibration:
    threshold: float          # recommended floor
    clean: bool               # True iff present/absent scores don't overlap
    gap: float                # min(present) − max(absent) (negative if they overlap)
    n_present: int
    n_absent: int
    present_min: float
    absent_max: float
    excluded: int             # golden items that are neither (traps) — not used


def _top_score(question: str, retriever: Retriever) -> float:
    hits = retriever.search(question, 1)
    return hits[0].score if hits else 0.0


def fit_floor(present: list[float], absent: list[float]) -> float:
    """Place the floor in the gap that best separates present (≥) from absent (<).

    Pure + deterministic: maximizes correct classifications, then maximum margin
    (so a clean split lands on the gap's midpoint). Same scores → same floor."""
    alls = sorted(present + absent)
    cands = ([alls[0] - 1.0]
             + [(a + b) / 2 for a, b in zip(alls, alls[1:], strict=False)]
             + [alls[-1] + 1.0])

    def correct(t: float) -> int:
        return sum(s >= t for s in present) + sum(s < t for s in absent)

    def margin(t: float) -> float:
        return min(abs(t - s) for s in alls)

    return round(max(cands, key=lambda t: (correct(t), margin(t))), 1)


def calibrate_threshold(
    golden_items: list[dict], retriever: Retriever, *, absent_tags=ABSENT_TAGS,
) -> Calibration:
    """Fit the support floor from the golden set's score separation (D20).

    `present` = answerable items; `absent` = unanswerable items tagged content-absent
    (`absent_tags`). The floor is placed in the widest gap that maximizes how many
    present clear AND absent don't (a clean separation → the gap's midpoint).
    """
    present, absent, excluded = [], [], 0
    for it in golden_items:
        if it.get("answerable"):
            present.append(_top_score(it["question"], retriever))
        elif set(it.get("tests", [])) & set(absent_tags):
            absent.append(_top_score(it["question"], retriever))
        else:
            excluded += 1
    if not present or not absent:
        raise ValueError("need both answerable and content-absent golden items")

    gap = min(present) - max(absent)
    return Calibration(
        threshold=fit_floor(present, absent), clean=gap > 0, gap=round(gap, 1),
        n_present=len(present), n_absent=len(absent),
        present_min=round(min(present), 1), absent_max=round(max(absent), 1),
        excluded=excluded,
    )
