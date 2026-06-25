"""verify — the deterministic atom resolver (ROADMAP M2-T1, D9; invariant I1).

The agent composes an answer and binds each **load-bearing atom** (a figure,
percentage, date, named entity) to a specific source location
`(doc_id, char_start, char_end)`. `verify` confirms, deterministically:

  1. each bound atom's slice at that offset equals the atom literal (exact, with
     defined whitespace normalization), and the doc hash matches (I3);
  2. **independent extraction** — verify re-scans the answer text for load-bearing
     figures and requires every one to be bound, so a confabulated number can't
     hide in untagged prose;
  3. **derived** values (a computed delta) aren't cited directly — they declare
     operands (each a bound atom) + an operation that verify recomputes.

The agent **parameterizes** (supplies atoms + bindings); it never **authors** this
resolver (oracle-is-sacred). `verify` confirms a citation is *real and located* —
not that it *entails* the claim (existence ≠ support; entailment is judged offline
at Layer-E). Pure and deterministic; corpus-agnostic. Result persistence is wired
to the audit log at M3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ingest.document import content_hash
from .spans import SpanError, SpanStore

# A load-bearing figure: comma-grouped number (optionally parenthesized-negative)
# or a percentage. Lookarounds prevent matching inside a larger number ("100" in
# "100,544"). Bare years / single integers are not *required* to be bound in v1
# (dates & named entities are verified when bound; full independent extraction for
# them is a documented gap → patent domain pack adds claim-term/numeral extractors).
_FIGURE = re.compile(r"\(?\d{1,3}(?:,\d{3})+\)?|\b\d+(?:\.\d+)?%")
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def numeric_core(text: str) -> str | None:
    """The figure token inside a literal, normalized for comparison ('$ 364,980' → '364,980')."""
    m = _FIGURE.search(text)
    return m.group(0).strip("()") if m else None


def to_number(text: str) -> float:
    """Parse an accounting figure to a number: '(19,154)' → -19154, '$ 364,980' → 364980."""
    neg = "(" in text and ")" in text
    digits = _NUM.search(text.replace(",", ""))
    if not digits:
        raise ValueError(f"no number in {text!r}")
    val = float(digits.group(0))
    return -abs(val) if neg else val


@dataclass(frozen=True)
class AtomBinding:
    """A load-bearing atom bound to an exact source location."""

    text: str          # the literal the agent asserts appears at the location
    doc_id: str
    char_start: int
    char_end: int
    content_hash: str | None = None  # the doc hash the binding was made against (drift check)


@dataclass(frozen=True)
class DerivedAtom:
    """A computed value: not cited directly; recomputed from bound operands."""

    text: str                       # the derived figure as written ("12,397")
    operation: str                  # "subtract" | "sum"
    operands: list[AtomBinding]


@dataclass(frozen=True)
class Sentence:
    text: str
    atoms: list[AtomBinding] = field(default_factory=list)
    derived: list[DerivedAtom] = field(default_factory=list)


@dataclass(frozen=True)
class Answer:
    sentences: list[Sentence]


@dataclass
class AtomVerdict:
    binding: AtomBinding
    status: str            # ok | mismatch | out_of_range | stale_hash
    found: str | None      # what the slice actually contained


@dataclass
class SentenceVerdict:
    text: str
    atom_verdicts: list[AtomVerdict]
    derived_ok: list[bool]
    unbound_figures: list[str]      # figures in the text with no binding/derivation
    ok: bool


@dataclass
class VerifyResult:
    sentences: list[SentenceVerdict]
    ok: bool

    def unbound(self) -> list[str]:
        return [f for s in self.sentences for f in s.unbound_figures]


_OPS = {
    "subtract": lambda xs: xs[0] - sum(xs[1:]),
    "sum": sum,
}


def _normalize(s: str) -> str:
    return " ".join(s.split())


def _resolve(binding: AtomBinding, store: SpanStore) -> AtomVerdict:
    if binding.content_hash is not None:
        current = content_hash(store.get_document(binding.doc_id))
        if binding.content_hash != current:
            return AtomVerdict(binding, "stale_hash", None)
    try:
        slice_ = store.get_span(binding.doc_id, binding.char_start, binding.char_end)
    except SpanError:
        return AtomVerdict(binding, "out_of_range", None)
    ok = _normalize(slice_) == _normalize(binding.text)
    return AtomVerdict(binding, "ok" if ok else "mismatch", slice_)


def verify(answer: Answer, store: SpanStore) -> VerifyResult:
    """Resolve every atom + derivation; flag unbound figures. I1/I3 enforced."""
    sentence_verdicts: list[SentenceVerdict] = []
    for sent in answer.sentences:
        atom_verdicts = [_resolve(a, store) for a in sent.atoms]

        derived_ok: list[bool] = []
        for d in sent.derived:
            ops = [_resolve(o, store) for o in d.operands]
            if not all(v.status == "ok" for v in ops) or d.operation not in _OPS:
                derived_ok.append(False)
                continue
            try:
                expected = _OPS[d.operation]([to_number(o.text) for o in d.operands])
                derived_ok.append(to_number(d.text) == expected)
            except ValueError:
                derived_ok.append(False)

        # Independent extraction: every figure in the prose must be covered.
        covered = {numeric_core(a.text) for a in sent.atoms}
        covered |= {numeric_core(d.text) for d in sent.derived}
        covered |= {numeric_core(o.text) for d in sent.derived for o in d.operands}
        detected = {m.group(0).strip("()") for m in _FIGURE.finditer(sent.text)}
        unbound = sorted(detected - covered)

        ok = (
            all(v.status == "ok" for v in atom_verdicts)
            and all(derived_ok)
            and not unbound
        )
        sentence_verdicts.append(
            SentenceVerdict(sent.text, atom_verdicts, derived_ok, unbound, ok)
        )

    return VerifyResult(sentence_verdicts, all(s.ok for s in sentence_verdicts))
