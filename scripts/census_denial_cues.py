#!/usr/bin/env python3
"""D24 census — measure the base rate of span-local denial/correction cues.

The provability research's Rung-1 question: does cue-marked refutation actually
OCCUR in real corpora, at what rate, and how close to figures? This is the number
that decides whether Rung 2 (the D25 abstain-trigger) is worth its answer-rate
cost — or is correctly deprioritized on evidence.

Reports, per corpus document:
  (a) total occurrences of each closed-set cue (DENIAL_CUES);
  (b) how many sit within the span-local window (CUE_WINDOW chars) of a numeric
      figure token — the only configuration the D25 gate would ever act on;
  (c) the actual text around each in-window pairing, so a human can judge whether
      it is a true refutation ("$2M … is incorrect") or benign boilerplate
      ("financial statements as restated") — the false-positive character of the
      corpus, which the research says is the load-bearing fact.

Deterministic, read-only, stdlib. Run:
    python scripts/census_denial_cues.py                        # EDGAR reference corpus
    python scripts/census_denial_cues.py --store corpus/engagements/US5447630A/store
"""

from __future__ import annotations

import argparse
import re

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from attest.cues import CUE_WINDOW, DENIAL_CUES, denial_cue_hits
from attest.ingest import DocumentStore

# A figure-like token: comma-grouped financials (364,980) or bare 2-4 digit numbers
# (patent numerals/quantities). Deliberately broad — the census over-approximates the
# set of atoms an agent might bind, so its in-window count is an UPPER bound on gate
# exposure.
_FIGURE = re.compile(r"\d{1,3}(?:,\d{3})+|\b\d{2,4}\b")


def census(store_dir: str) -> None:
    ds = DocumentStore(store_dir)
    for doc_id in ds.list_docs():
        text = ds.load(doc_id).canonical_text
        atoms = [m.start() for m in _FIGURE.finditer(text)]
        total = {c: len(re.findall(rf"\b{c}\b", text, re.IGNORECASE)) for c in DENIAL_CUES}
        total = {c: n for c, n in total.items() if n}
        hits = denial_cue_hits(text, atoms)
        print(f"\n=== {doc_id}  ({len(text):,} chars · {len(atoms):,} figure-like tokens) ===")
        print(f"cue occurrences anywhere: {total or 'NONE'}")
        print(f"cues within {CUE_WINDOW} chars of a figure token: {len(hits)}")
        for h in hits:
            s = max(0, h.cue_start - 70)
            ctx = " ".join(text[s:h.cue_end + 70].split())
            print(f"  · “{h.cue}” @{h.cue_start} ({h.distance} chars from a figure): …{ctx}…")


def main() -> int:
    ap = argparse.ArgumentParser(description="D24 census: denial-cue base rate in a corpus")
    ap.add_argument("--store", default="corpus/store", help="corpus store to scan")
    ns = ap.parse_args()
    census(ns.store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
