#!/usr/bin/env python3
"""Patent claim-support review artifact (PE-3) → a two-pane evidence view.

For one claim, renders each limitation as a card whose cited spans are its
**supporting specification paragraphs** (ranked) — click a limitation and its
support highlights in the patent on the left. Runs the dependency-integrity check
(PE-2) and prints the claim's place in the dependency tree. Corpus-agnostic: point
it at any ingested patent store.

Usage:
    python scripts/patent_support_view.py --store corpus/engagements/US5447630A/store \\
        --doc US5447630A --claim 1 --out review.html

**Locate & evidence, never adjudicate (D10):** "no clear support located" is a
retrieval gap for review, not a written-description/validity conclusion.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from attest.evidence_view import Interaction, render_evidence_view
from attest.ingest import DocumentStore
from attest.patents import (
    check_dependencies,
    map_claim_support,
    parse_claims,
    parse_paragraphs,
)
from attest.spans import SpanStore
from attest.verify import Answer, AtomBinding, Sentence, verify


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a claim's limitation→spec support mapping")
    ap.add_argument("--store", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--claim", type=int, default=1)
    ap.add_argument("--k", type=int, default=2, help="supporting paragraphs per limitation")
    ap.add_argument("--floor", type=float, default=0.0)
    ap.add_argument("--out", default="patent_support.html")
    ns = ap.parse_args()

    store = SpanStore.from_store(DocumentStore(ns.store))
    text = store.get_document(ns.doc)
    claims = parse_claims(text)
    paragraphs = parse_paragraphs(text)
    claim = next(c for c in claims if c.number == ns.claim)

    issues = check_dependencies(claims)
    print(f"dependency integrity: {len(issues) or 'clean'}"
          + ("" if not issues else " — " + "; ".join(i.message for i in issues)))

    mapping = map_claim_support(claim, paragraphs, ns.doc, k=ns.k, floor=ns.floor)
    interactions: list[Interaction] = []
    gaps = 0
    for i, (lim, edges) in enumerate(mapping, 1):
        q = f"Claim {claim.number} · limitation {i}: {lim.text}"
        if edges:
            labels = ", ".join(f"{e.paragraph_label} ({e.score:g})" for e in edges)
            atoms = [AtomBinding(store.get_span(ns.doc, e.char_start, e.char_end),
                                 ns.doc, e.char_start, e.char_end) for e in edges]
            ans = Answer([Sentence(f"Support located in {labels}.", atoms=atoms)])
            interactions.append(Interaction(
                q, "answer", answer=ans, verify=verify(ans, store),
                note="Click to highlight the supporting paragraph(s) in the specification.",
                trace=f"BM25 over {len(paragraphs)} spec paragraphs · ranked support (not a "
                      f"sufficiency judgment, D10)"))
        else:
            gaps += 1
            interactions.append(Interaction(
                q, "abstain",
                reason="No clear textual support located for this limitation — flagged for "
                       "review (a retrieval gap, not a written-description/validity conclusion).",
                trace="no spec paragraph cleared the support floor"))

    title = f"ATTEST — {ns.doc} · claim {claim.number} support ({claim.kind})"
    Path(ns.out).write_text(render_evidence_view(interactions, store, title=title),
                            encoding="utf-8")
    print(f"claim {claim.number} ({claim.kind}): {len(mapping)} limitations, "
          f"{gaps} with no clear support located")
    print(f"OK — wrote {ns.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
