#!/usr/bin/env python3
"""Calibrate the `check_support` floor from a golden set (D20).

Fits the per-corpus relevance floor from labels instead of hand-tuning it: it
separates answerable golden queries (top span should clear) from content-absent
ones (should not), and reports the value + the separation so the choice is
auditable. Record the result in the engagement's `ATTEST_SUPPORT_THRESHOLD`.

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

from attest.ingest import DocumentStore
from attest.retrieval import Retriever
from attest.spans import SpanStore
from attest.support import calibrate_threshold

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description="Fit the check_support floor from a golden set")
    ap.add_argument("--golden", default=str(ROOT / "golden_seed.json"))
    ap.add_argument("--store", default=str(ROOT / "corpus" / "store"))
    ns = ap.parse_args()

    items = json.loads(Path(ns.golden).read_text(encoding="utf-8"))["items"]
    retriever = Retriever(SpanStore.from_store(DocumentStore(ns.store)))
    c = calibrate_threshold(items, retriever)

    sep = "clean separation" if c.clean else "OVERLAP — not separable by a single floor"
    print(f"recommended ATTEST_SUPPORT_THRESHOLD = {c.threshold}")
    print(f"  answerable (n={c.n_present}): top scores ≥ {c.present_min}")
    print(f"  content-absent (n={c.n_absent}): top scores ≤ {c.absent_max}")
    print(f"  gap = {c.gap}  ({sep});  {c.excluded} trap items excluded (handled by reasoning)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
