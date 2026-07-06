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


# --- JSON bridge + live coverage (M2-T8: the agent emits the frame at runtime) ----

def frame_from_json(d: dict) -> QuestionFrame:
    return QuestionFrame(d.get("question", ""), [
        Constraint(c["role"], c["text"], bool(c.get("required", True)))
        for c in d.get("constraints", [])
    ])


def frame_to_json(f: QuestionFrame) -> dict:
    return {"question": f.question, "constraints": [
        {"role": c.role, "text": c.text, "required": c.required} for c in f.constraints
    ]}


def coverage_to_json(cov: CoverageResult) -> dict:
    return {
        "complete": cov.complete,
        "covered": [{"role": c.role, "text": c.text} for c in cov.covered],
        "missing": [{"role": c.role, "text": c.text} for c in cov.missing],
    }


def coverage_for_answer(frame: QuestionFrame, answer, store) -> CoverageResult:
    """Coverage over the answer's cited evidence — the *containing spans* of every
    bound atom and derived operand (the connecting clause lives in the surrounding
    line, not the atom literal). Deterministic; same semantics as the evidence view.
    `answer` is a `verify.Answer`; `store` a `SpanStore`."""
    cited: list[str] = []
    for sent in answer.sentences:
        atoms = list(sent.atoms) + [o for d in sent.derived for o in d.operands]
        for a in atoms:
            sp = store.span_containing(a.doc_id, a.char_start)
            if sp is not None:
                cited.append(sp.text)
    return check_coverage(frame, cited)
