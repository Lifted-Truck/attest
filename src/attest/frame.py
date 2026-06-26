"""Question frame + constraint coverage (ROADMAP M2-T8, D13).

A citation must prove the *question's constraints* are satisfied, not merely that
the answer token appears. "What color is the wheel well?" → citing `red` is
worthless unless the cited span also carries `wheel well` (the connecting clause).

In v1 the **agent** decomposes the query into a typed `QuestionFrame` (it is the
parser — no extra model needed); ATTEST then does the **deterministic** check:
does the cited evidence cover every constraint? This is corpus-agnostic.

Coverage is **necessary, not sufficient** for entailment — negation ("not red"),
attachment ("the fender is red, beside the wheel well"), and coreference ("it is
red") survive a coverage check and remain the Layer-E judge's / human's job.
"""

from __future__ import annotations

from dataclasses import dataclass

# Constraint roles the agent may tag (provisional taxonomy, D13).
ROLES = ("entity", "metric", "attribute", "subject", "period", "unit", "scope", "comparison")


@dataclass(frozen=True)
class Constraint:
    role: str
    text: str            # the literal the cited evidence must demonstrably contain
    required: bool = True  # entity is often implicit in a single-corpus build


@dataclass(frozen=True)
class QuestionFrame:
    question: str
    constraints: list[Constraint]


@dataclass
class CoverageResult:
    covered: list[Constraint]
    missing: list[Constraint]  # required constraints absent from the cited evidence

    @property
    def complete(self) -> bool:
        return not self.missing


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def check_coverage(frame: QuestionFrame, cited_texts: list[str]) -> CoverageResult:
    """Each required constraint's text must appear in the cited evidence."""
    blob = _norm(" \n ".join(cited_texts))
    covered, missing = [], []
    for c in frame.constraints:
        if _norm(c.text) in blob:
            covered.append(c)
        elif c.required:
            missing.append(c)
        else:
            covered.append(c)  # optional + absent → treated as satisfied (e.g. implicit entity)
    return CoverageResult(covered, missing)
