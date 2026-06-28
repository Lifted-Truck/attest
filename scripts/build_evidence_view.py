#!/usr/bin/env python3
"""Generate the evidence-view GUI (ROADMAP M2-T7) → evidence_view.html.

Builds a handful of demonstration interactions over the golden set and renders
them to a single self-contained HTML page you open in a browser. The prose is
curated (from the golden answers) — the *live* agent composes it at M4 — but the
citations, highlights, verify status, and abstention spans are all real
deterministic output of the M1/M2 tools.

Usage:
  python scripts/build_evidence_view.py                 # curated demos → ./evidence_view.html
  python scripts/build_evidence_view.py --from-audit     # a REAL session → ./evidence_view.html
  python scripts/build_evidence_view.py --from-audit audit_log/agent.jsonl --out review.html

`--from-audit` rebuilds the view from a live Claude Code / Desktop session's audit
log (every presented `verify` becomes a card) — the bridge from working in Desktop
to reviewing the citations.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from attest.audit import AuditLog
from attest.evidence_view import Interaction, interactions_from_audit, render_evidence_view
from attest.frame import Constraint, QuestionFrame
from attest.ingest import DocumentStore
from attest.retrieval import Retriever
from attest.spans import SpanStore
from attest.support import THRESHOLD, check_support
from attest.verify import Answer, AtomBinding, DerivedAtom, Sentence, verify

ROOT = Path(__file__).resolve().parent.parent
DOC = "AAPL-10K-FY2024"
OUT = ROOT / "evidence_view.html"
AUDIT = ROOT / "audit_log" / "agent.jsonl"


def build_from_audit(audit_path: Path, out: Path) -> int:
    store = SpanStore.from_store(DocumentStore(ROOT / "corpus" / "store"))
    if not audit_path.exists():
        print(f"No audit log at {audit_path} — run a live session first "
              "(or scripts/run_layer_e.py).")
        return 1
    entries = [e.payload for e in AuditLog(audit_path).entries()]
    interactions = interactions_from_audit(entries, store)
    if not interactions:
        print(f"No presented (verify-ok) interactions in {audit_path} — nothing to render.")
        return 1
    out.write_text(render_evidence_view(interactions, store), encoding="utf-8")
    print(f"OK — wrote {out} ({len(interactions)} interaction(s) from {audit_path})")
    return 0

TOTAL_ASSETS = "Total assets $ 364,980 $ 352,583"
LIAB_EQUITY = "Total liabilities and shareholders’ equity $ 364,980 $ 352,583"
TERM_CUR = "Term debt 10,912 9,822"
TERM_NON = "Term debt 85,750 95,281"


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the ATTEST evidence-view GUI")
    ap.add_argument("--from-audit", nargs="?", const=str(AUDIT), default=None,
                    metavar="PATH", help="rebuild from a live session's audit log")
    ap.add_argument("--out", default=str(OUT), help="output HTML path")
    ns = ap.parse_args()
    if ns.from_audit is not None:
        return build_from_audit(Path(ns.from_audit), Path(ns.out))

    store = SpanStore.from_store(DocumentStore(ROOT / "corpus" / "store"))
    retriever = Retriever(store)
    canonical = store.get_document(DOC)

    def bind(literal: str, line: str) -> AtomBinding:
        start, _ = store.resolve_quote(DOC, line)
        i = line.index(literal)
        return AtomBinding(literal, DOC, start + i, start + i + len(literal))

    def bind_nearest(literal: str, near: int) -> AtomBinding:
        """Bind to the occurrence of `literal` nearest `near` (D14 nearest substantiation)."""
        offs, i = [], canonical.find(literal)
        while i != -1:
            offs.append(i)
            i = canonical.find(literal, i + 1)
        best = min(offs, key=lambda o: abs(o - near))
        return AtomBinding(literal, DOC, best, best + len(literal))

    def top(q: str) -> float:
        hits = retriever.search(q, 1)
        return hits[0].score if hits else 0.0

    interactions: list[Interaction] = []

    # 1. Clean grounded lookup — figure AND the "as of" date are both bound; the date
    #    binds to the balance-sheet column header right above the figure (D14), not the cover.
    q1 = "What were Apple's total assets as of September 28, 2024?"
    fig = bind("364,980", TOTAL_ASSETS)
    a1 = Answer([Sentence(
        "Apple's total assets were $364,980 million as of September 28, 2024.",
        atoms=[fig, bind_nearest("September 28, 2024", fig.char_start)],
    )])
    interactions.append(Interaction(
        q1, "answer", answer=a1, verify=verify(a1, store),
        note="The figure and the period ('as of …') are each bound to a span.",
        trace=f"check_support top {top(q1):.0f} ≥ floor {THRESHOLD:.0f} → supported · "
              f"verify: 2/2 atoms resolved (figure + date)",
        frame=QuestionFrame(q1, [
            Constraint("metric", "Total assets"),
            Constraint("period", "September 28, 2024"),
            Constraint("entity", "Apple", required=False),
        ]),
    ))

    # 2. Derived answer — operands cited, the delta recomputed (not cited).
    q2 = "Did Apple's total assets increase from fiscal 2023 to 2024, and by how much?"
    a2 = Answer([Sentence(
        "Total assets increased by $12,397 million (from $352,583M to $364,980M).",
        derived=[DerivedAtom("12,397", "subtract",
                             [bind("364,980", TOTAL_ASSETS), bind("352,583", TOTAL_ASSETS)])],
    )])
    interactions.append(Interaction(
        q2, "answer", answer=a2, verify=verify(a2, store),
        note="The $12,397M delta is recomputed from both operands, never cited as a fact.",
        trace=f"check_support top {top(q2):.0f} ≥ floor {THRESHOLD:.0f} → supported · "
              f"the delta is recomputed from bound operands (see derivation ƒ below)",
        frame=QuestionFrame(q2, [Constraint("metric", "Total assets")]),
    ))

    # 3. Plural & ranked — both term-debt portions surfaced.
    q3 = "How much term debt does Apple carry?"
    a3 = Answer([Sentence(
        "Apple carries term debt in two portions: a current portion of $10,912 million "
        "and a non-current portion of $85,750 million.",
        atoms=[bind("10,912", TERM_CUR), bind("85,750", TERM_NON)],
    )])
    interactions.append(Interaction(
        q3, "answer", answer=a3, verify=verify(a3, store),
        note="One question, two valid figures — both surfaced and distinguished.",
        trace=f"check_support top {top(q3):.0f} ≥ floor {THRESHOLD:.0f} → supported · "
              f"two term-debt spans clear the floor (plural, ranked)",
        frame=QuestionFrame(q3, [Constraint("metric", "term debt")]),
    ))

    # 3b. The point of D13: verify can PASS while coverage FAILS. This answer cites a
    # span that really contains 364,980 — but it's the liabilities+equity total, not
    # assets. The figure is real; the cited span doesn't establish the question's metric.
    a_naive = Answer([Sentence(
        "Apple's total assets were $364,980 million.",
        atoms=[bind("364,980", LIAB_EQUITY)],
    )])
    interactions.append(Interaction(
        "What were Apple's total assets? (naive citation)",
        "answer", answer=a_naive, verify=verify(a_naive, store),
        note="The figure $364,980 is real and resolves — but the cited line is "
             "'Total liabilities and shareholders’ equity', not 'Total assets'.",
        trace="verify ✓ (364,980 resolves) BUT coverage ✗ — the cited span does not "
              "carry the question's metric. This is the gap D13 closes.",
        frame=QuestionFrame("total assets?", [Constraint("metric", "Total assets")]),
    ))

    # 4. Abstain — content absent (deterministic, D12).
    ceo_q = "What was the total compensation of Apple's CEO in fiscal 2024?"
    g011 = check_support(ceo_q, retriever)
    g011_top = g011.closest[0].score if g011.closest else 0.0
    interactions.append(Interaction(
        ceo_q, "abstain",
        reason="Executive compensation is disclosed in the DEF 14A proxy, not the 10-K.",
        closest=g011.closest,
        trace=f"check_support top {g011_top:.0f} < floor {THRESHOLD:.0f} → insufficient "
              f"(deterministic content-absence abstention, D12)",
    ))

    # 5. Abstain — right metric, wrong period (agent reasoning, D12).
    q5 = "total assets December 28 2024"
    interactions.append(Interaction(
        "What were Apple's total assets as of December 28, 2024?",
        "abstain",
        reason="The requested date (December 28, 2024) is outside this filing's coverage "
               "(FY2024 ended September 28, 2024). The September figure is NOT the answer.",
        closest=retriever.search(q5, 2),
        trace=f"check_support top {top(q5):.0f} ≥ floor {THRESHOLD:.0f} → supported, "
              f"BUT the agent abstains on the period mismatch (semantic trap, D12 → Layer-E)",
    ))

    # 6. Reject the false premise — cite the figures that disprove it.
    q6 = "Why did Apple's total assets decline in fiscal 2024?"
    interactions.append(Interaction(
        q6, "reject",
        reason="The premise is false: total assets rose, they did not decline.",
        note="Total assets increased from $352,583M (FY2023) to $364,980M (FY2024).",
        closest=retriever.search("total assets", 1),
        trace="agent rejects the false premise; the cited figures show the value rose "
              "(semantic, D12 → Layer-E). Note the $-figures here are illustrative, not bound.",
    ))

    out = Path(ns.out)
    out.write_text(render_evidence_view(interactions, store), encoding="utf-8")
    print(f"OK — wrote {out} ({len(interactions)} interactions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
