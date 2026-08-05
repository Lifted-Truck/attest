#!/usr/bin/env python3
"""Calibrate the `check_support` floor from a golden set (D20).

Fits the per-corpus relevance floor from labels instead of hand-tuning it: it
separates answerable golden queries (top span should clear) from content-absent
ones (should not), and reports the value + the separation so the choice is
auditable. Record the result in the engagement's `CAIRN_SUPPORT_THRESHOLD`.

Usage:
    python scripts/calibrate_threshold.py                                  # EDGAR golden
    python scripts/calibrate_threshold.py --golden patent_golden.json \\
        --store corpus/engagements/US5447630A/store
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from cairn.calibration import CalibrationRecord, corpus_hash
from cairn.calibration import write as write_calibration
from cairn.ingest import DocumentStore
from cairn.retrieval import Retriever
from cairn.spans import SpanStore
from cairn.support import calibrate_threshold

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description="Fit the check_support floor from a golden set")
    ap.add_argument("--golden", default=str(ROOT / "golden_seed.json"))
    ap.add_argument("--store", default=str(ROOT / "corpus" / "store"))
    ap.add_argument("--write", metavar="YYYY-MM-DD",
                    help="write calibration.json into the store, dated (RT-9). Without "
                         "this the fit is only printed and the store stays UNCALIBRATED, "
                         "which every check_support result then says out loud.")
    ns = ap.parse_args()

    items = json.loads(Path(ns.golden).read_text(encoding="utf-8"))["items"]
    doc_store = DocumentStore(ns.store)
    retriever = Retriever(SpanStore.from_store(doc_store))
    c = calibrate_threshold(items, retriever)

    sep = "clean separation" if c.clean else "OVERLAP — not separable by a single floor"
    print(f"recommended CAIRN_SUPPORT_THRESHOLD = {c.threshold}")
    print(f"  answerable (n={c.n_present}): top scores ≥ {c.present_min}")
    print(f"  content-absent (n={c.n_absent}): top scores ≤ {c.absent_max}")
    print(f"  gap = {c.gap}  ({sep});  {c.excluded} trap items excluded (handled by reasoning)")

    if ns.write:
        # The date is supplied, never read from the clock: cores stay clock-free so a
        # calibration record replays identically (I6).
        ids = doc_store.list_docs()
        rec = CalibrationRecord(
            threshold=c.threshold, corpus_id=Path(ns.store).parent.name, doc_ids=ids,
            corpus_hash=corpus_hash(ids, [doc_store.load(d).content_hash for d in ids]),
            calibrated_on=ns.write, method="golden-gap",
            n_present=c.n_present, n_absent=c.n_absent,
            separable=c.clean, gap=c.gap)
        if not c.clean:
            print("\n  ⚠ the scores OVERLAP — this floor does not separate answerable "
                  "from content-absent")
            print("    items. Recording it anyway, flagged NON-SEPARABLE, because "
                  "hiding a failed fit")
            print("    would let 'calibrated' mean 'we ran the fitter'.")
        print(f"\nwrote {write_calibration(ns.store, rec)}")
        print(f"  corpus_hash = {rec.corpus_hash[:16]}…  "
              f"(a doc added/removed/edited after this makes the record STALE)")
    else:
        print("\n  not written — re-run with --write YYYY-MM-DD to record it in the store.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
