#!/usr/bin/env python3
"""PE-2 census — measure whether an antecedent-basis check can be built from text alone.

§112(b) antecedent basis is the classic structural claim check: an element referred to as
"the X" or "said X" should have been introduced earlier as "a X". It looks mechanical,
which is why it keeps getting proposed. This script measures what it actually does on real
claims, so the decision rests on a firing rate rather than on how tractable it feels.

Two strategies are measured, weakest first, because the improvement from one to the other
is itself the finding:

  · **whole-phrase** — "the touch screen" must match an earlier "a touch screen";
  · **head-noun** — match on the phrase's final word, since English noun phrases are
    head-final, so "a portable electronic device" introduces "the device".

Both walk the dependency chain: a dependent claim inherits its ancestors' introductions.

Read-only, deterministic, no model calls. Run:

    python scripts/census_antecedent_basis.py                      # both engagement patents
    python scripts/census_antecedent_basis.py --store <store> --doc <id>
"""

from __future__ import annotations

import argparse
import collections
import re
from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from cairn.ingest import DocumentStore
from cairn.patents import parse_claims

# A claim element phrase ends where a function word begins. This list is generous — a
# stingier one over-captures ("the separating chamber further" swallowing the adverb),
# which inflates the flag count for a reason that has nothing to do with antecedents.
_STOP = (r"(?=[,;.:]|\s+(?:is|are|was|were|for|to|of|in|on|at|that|which|and|or|wherein|"
         r"having|comprising|including|configured|adapted|being|so|whereby|further|while|"
         r"when|results|includes|comprise|from|with|into|through)\b)")
_INTRO = re.compile(rf"\b(?:a|an)\s+([a-z][a-z0-9\- ]{{2,44}}?){_STOP}", re.I)
_BACK = re.compile(rf"\b(?:the|said)\s+([a-z][a-z0-9\- ]{{2,44}}?){_STOP}", re.I)

# "the invention", "the art" and friends are conventional patent prose, not elements.
# Excluded so they do not pad the count in either direction.
_GENERIC = frozenset({
    "invention", "art", "present invention", "same", "like", "group", "group consisting",
    "figure", "drawings", "specification", "claim", "embodiment", "following", "above",
})


def _norm(p: str) -> str:
    return re.sub(r"\s+", " ", p.strip().lower())


def _head(p: str) -> str:
    parts = _norm(p).split()
    return parts[-1] if parts else ""


def census(text: str, *, by_head: bool) -> tuple[int, list[tuple[int, str]]]:
    """(back-references considered, flagged). `by_head` selects the matching strategy."""
    claims = parse_claims(text)
    by_num = {c.number: c for c in claims}
    key = _head if by_head else _norm
    flagged: list[tuple[int, str]] = []
    considered = 0

    for c in claims:
        chain, cur = [], c
        while cur is not None:                       # a dependent inherits its ancestors
            chain.append(cur)
            cur = by_num.get(cur.depends_on) if cur.depends_on else None
        introduced = {key(m.group(1)) for anc in chain for m in _INTRO.finditer(anc.text)}

        for m in _BACK.finditer(c.text):
            phrase = _norm(m.group(1))
            if phrase in _GENERIC or _head(phrase) in _GENERIC:
                continue
            considered += 1
            if key(phrase) not in introduced:
                flagged.append((c.number, phrase))
    return considered, flagged


def report(doc_id: str, text: str) -> None:
    print(f"\n{doc_id}  ({len(parse_claims(text))} claims)")
    for label, by_head in (("whole-phrase", False), ("head-noun  ", True)):
        n, flagged = census(text, by_head=by_head)
        pct = len(flagged) * 100 // max(n, 1)
        print(f"  {label}: {len(flagged):>3} of {n:>3} back-references flagged  ({pct}%)")
    n, flagged = census(text, by_head=True)
    print("  most-flagged phrases under the better strategy:")
    for p, k in collections.Counter(p for _, p in flagged).most_common(6):
        print(f"     {p!r:<44} x{k}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Census the antecedent-basis check (PE-2)")
    ap.add_argument("--store")
    ap.add_argument("--doc")
    ns = ap.parse_args()

    targets = ([(ns.doc, ns.store)] if ns.store and ns.doc else
               [("US5447630A", "corpus/engagements/US5447630A/store"),
                ("US8046721B2", "corpus/engagements/US8046721B2/store")])

    print("PE-2 antecedent-basis census — what a text-only check actually flags")
    for doc_id, store in targets:
        p = Path(store)
        if not p.exists():
            print(f"\n{doc_id}: store not present at {store} (engagement stores are local)")
            continue
        report(doc_id, DocumentStore(p).load(doc_id).canonical_text)

    print("""
Reading this: a flag here is not a §112(b) finding. It says only that a text-only matcher
could not pair a back-reference with an introduction — and the dominant reason it cannot
is COORDINATED INTRODUCTION, which is ordinary drafting, not a defect:

    claim 1  "...separating an incoming flow into at least first and second components"
    claim 1  "...said second component includes primarily liquids"

The elements are introduced once, plural, sharing a determiner, and referred to singly
afterwards. Resolving that needs coordination and number agreement — parsing, not
patterns. Until something can, this check would assert a defect-shaped flag against real
elements at roughly a 1-in-3 rate, on a tool whose cardinal rule is to locate and evidence
and never adjudicate (D10). See D58.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
