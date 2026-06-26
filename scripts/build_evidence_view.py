#!/usr/bin/env python3
"""Generate the evidence-view GUI (ROADMAP M2-T7) → evidence_view.html.

Builds a handful of demonstration interactions over the golden set and renders
them to a single self-contained HTML page you open in a browser. The prose is
curated (from the golden answers) — the *live* agent composes it at M4 — but the
citations, highlights, verify status, and abstention spans are all real
deterministic output of the M1/M2 tools.

Usage:  python scripts/build_evidence_view.py   # writes ./evidence_view.html
"""

from __future__ import annotations

from pathlib import Path

from attest.evidence_view import Interaction, render_evidence_view
from attest.ingest import DocumentStore
from attest.retrieval import Retriever
from attest.spans import SpanStore
from attest.support import check_support
from attest.verify import Answer, AtomBinding, DerivedAtom, Sentence, verify

ROOT = Path(__file__).resolve().parent.parent
DOC = "AAPL-10K-FY2024"
OUT = ROOT / "evidence_view.html"

TOTAL_ASSETS = "Total assets $ 364,980 $ 352,583"
TERM_CUR = "Term debt 10,912 9,822"
TERM_NON = "Term debt 85,750 95,281"


def main() -> int:
    store = SpanStore.from_store(DocumentStore(ROOT / "corpus" / "store"))
    retriever = Retriever(store)

    def bind(literal: str, line: str) -> AtomBinding:
        start, _ = store.resolve_quote(DOC, line)
        i = line.index(literal)
        return AtomBinding(literal, DOC, start + i, start + i + len(literal))

    interactions: list[Interaction] = []

    # 1. Clean grounded lookup.
    a1 = Answer([Sentence(
        "Apple's total assets were $364,980 million as of September 28, 2024.",
        atoms=[bind("364,980", TOTAL_ASSETS)],
    )])
    interactions.append(Interaction(
        "What were Apple's total assets as of September 28, 2024?",
        "answer", answer=a1, verify=verify(a1, store),
        note="A single figure, bound to its exact line.",
    ))

    # 2. Derived answer — operands cited, the delta recomputed (not cited).
    a2 = Answer([Sentence(
        "Total assets increased by $12,397 million (from $352,583M to $364,980M).",
        derived=[DerivedAtom("12,397", "subtract",
                             [bind("364,980", TOTAL_ASSETS), bind("352,583", TOTAL_ASSETS)])],
    )])
    interactions.append(Interaction(
        "Did Apple's total assets increase from fiscal 2023 to 2024, and by how much?",
        "answer", answer=a2, verify=verify(a2, store),
        note="The $12,397M delta is recomputed from both operands, never cited as a fact.",
    ))

    # 3. Plural & ranked — both term-debt portions surfaced.
    a3 = Answer([Sentence(
        "Apple carries term debt in two portions: a current portion of $10,912 million "
        "and a non-current portion of $85,750 million.",
        atoms=[bind("10,912", TERM_CUR), bind("85,750", TERM_NON)],
    )])
    interactions.append(Interaction(
        "How much term debt does Apple carry?",
        "answer", answer=a3, verify=verify(a3, store),
        note="One question, two valid figures — both surfaced and distinguished.",
    ))

    # 4. Abstain — content absent (deterministic, D12).
    ceo_q = "What was the total compensation of Apple's CEO in fiscal 2024?"
    g011 = check_support(ceo_q, retriever)
    interactions.append(Interaction(
        "What was the total compensation of Apple's CEO in fiscal 2024?",
        "abstain",
        reason="check_support → insufficient: executive compensation is disclosed in the "
               "DEF 14A proxy, not the 10-K. No span cleared the relevance floor.",
        closest=g011.closest,
    ))

    # 5. Abstain — right metric, wrong period (agent reasoning, D12).
    interactions.append(Interaction(
        "What were Apple's total assets as of December 28, 2024?",
        "abstain",
        reason="The requested date (December 28, 2024) is outside this filing's coverage "
               "(FY2024 ended September 28, 2024). The September figure is NOT the answer.",
        closest=retriever.search("total assets December 28 2024", 2),
    ))

    # 6. Reject the false premise — cite the figures that disprove it.
    interactions.append(Interaction(
        "Why did Apple's total assets decline in fiscal 2024?",
        "reject",
        reason="The premise is false: total assets rose, they did not decline.",
        note="Total assets increased from $352,583M (FY2023) to $364,980M (FY2024).",
        closest=retriever.search("total assets", 1),
    ))

    OUT.write_text(render_evidence_view(interactions, store), encoding="utf-8")
    print(f"OK — wrote {OUT.relative_to(ROOT)} ({len(interactions)} interactions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
