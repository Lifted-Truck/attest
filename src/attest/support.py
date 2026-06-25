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
