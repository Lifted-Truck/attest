#!/usr/bin/env python3
"""Build the M0 toy corpus (ROADMAP M0-T2) from a single SEC EDGAR filing.

Scope (brief §2): a tiny doc set of 5-10 verbatim excerpts that the audition rig
(`attest_rig.py`) runs over. This is an M0 fixture builder; the durable evidence
layer is M1. To honor "corpus-specific code lives in one file" (brief §8), the
fetch + normalization now come from the M1 EDGAR adapter (`attest.ingest.edgar`);
this script only slices the normalized text into the rig's excerpts.

Deterministic and offline-after-first-run: the raw filing is cached under
data/raw/ (gitignored); re-runs read the cache so we don't re-hit EDGAR.

Usage:
    python scripts/build_toy_corpus.py
    SEC_USER_AGENT="you you@example.com" python scripts/build_toy_corpus.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from attest.ingest.edgar import FILINGS, fetch_html, normalize

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "corpus" / "toy"

FILING = FILINGS["AAPL-10K-FY2024"]  # provenance single-sourced from the adapter
DOC_ID = FILING["doc_id"]

# Each excerpt is sliced [start_anchor .. end_anchor). end_anchor is the first
# occurrence at/after the start. Anchors chosen for legibility, not cleverness.
SECTIONS = [
    {
        "key": "01_cover",
        "title": "Cover page (period of report)",
        "start": "UNITED STATES",
        "end": "PART I\n",
        "granularity": "line",
        "covers": ["G010"],
    },
    {
        "key": "02_statements_of_operations",
        "title": "Consolidated Statements of Operations",
        "start": "CONSOLIDATED STATEMENTS OF OPERATIONS",
        "end": "See accompanying Notes to Consolidated Financial Statements.",
        "granularity": "line",  # tabular: one line item per span
        "covers": ["distractor"],
    },
    {
        "key": "03_balance_sheets",
        "title": "Consolidated Balance Sheets",
        "start": "CONSOLIDATED BALANCE SHEETS",
        "end": "See accompanying Notes to Consolidated Financial Statements.",
        "granularity": "line",
        "covers": ["G001-G008", "G016-G020"],
    },
    {
        "key": "04_statements_of_cash_flows",
        "title": "Consolidated Statements of Cash Flows",
        "start": "CONSOLIDATED STATEMENTS OF CASH FLOWS",
        "end": "See accompanying Notes to Consolidated Financial Statements.",
        "granularity": "line",
        "covers": ["distractor"],
    },
    {
        "key": "05_auditor_report",
        "title": "Report of Independent Registered Public Accounting Firm (financial statements)",
        "start": "Report of Independent Registered Public Accounting Firm",
        # Terminate at the *second* report header (internal control over financial reporting).
        "end": "To the Shareholders and the Board of Directors of Apple Inc.",
        "end_after": "/s/ Ernst & Young LLP",
        "granularity": "block",
        "covers": ["G009"],
    },
]

# Sanity anchors: figures/strings that MUST survive into the stored corpus.
REQUIRED_STRINGS = [
    "For the fiscal year ended September 28, 2024",  # G010
    "364,980", "352,583",                            # G001/G005/G020 total assets both years
    "176,392",                                       # G004 total current liabilities
    "9,967",                                         # G002 commercial paper
    "45,680",                                        # G003 PP&E net
    "78,304", "58,829",                              # G006 other current liabilities
    "14,287",                                        # G017 other current assets
    "8,249",                                         # G018 deferred revenue
    "10,912", "9,822",                               # G007/G019 term debt current
    "85,750",                                        # G007 term debt non-current
    "91,479",                                        # G008 marketable securities (non-current)
    "Ernst & Young LLP",                             # G009
]


def slice_section(text: str, sec: dict) -> str:
    start = text.find(sec["start"])
    if start == -1:
        raise SystemExit(f"start anchor not found for {sec['key']!r}: {sec['start']!r}")
    # Optional: extend past an interior marker (e.g. the auditor signature) before ending.
    floor = start
    if "end_after" in sec:
        after = text.find(sec["end_after"], start)
        if after == -1:
            raise SystemExit(f"end_after anchor not found for {sec['key']!r}: {sec['end_after']!r}")
        floor = after + len(sec["end_after"])
    end = text.find(sec["end"], floor)
    if end == -1:
        end = len(text)
    elif sec["end"].startswith("See accompanying"):
        # Statements: keep the terminating "See accompanying Notes" line in the excerpt.
        end += len(sec["end"])
    return text[start:end].strip() + "\n"


def main() -> int:
    raw = fetch_html(DOC_ID, RAW_DIR)
    text = normalize(raw)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc_dir = OUT_DIR / DOC_ID
    doc_dir.mkdir(parents=True, exist_ok=True)

    excerpts = []
    all_text = []
    for sec in SECTIONS:
        body = slice_section(text, sec)
        fname = f"{sec['key']}.txt"
        (doc_dir / fname).write_text(body, encoding="utf-8")
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        excerpts.append(
            {
                "excerpt_id": f"{DOC_ID}::{sec['key']}",
                "section_title": sec["title"],
                "path": str((doc_dir / fname).relative_to(ROOT)),
                "granularity": sec["granularity"],
                "covers_golden": sec["covers"],
                "char_len": len(body),
                "sha256": sha,
            }
        )
        all_text.append(body)
        print(f"  {sec['key']:<32} {len(body):>6} chars  sha256={sha[:12]}…")

    # Gate: every required figure/string survived into the stored corpus.
    corpus_blob = "\n".join(all_text)
    missing = [s for s in REQUIRED_STRINGS if s not in corpus_blob]
    if missing:
        print("\nFAIL — required strings missing from stored corpus:", missing, file=sys.stderr)
        return 1

    manifest = {
        "_note": (
            "M0 toy corpus (ROADMAP M0-T2). Verbatim excerpts from a single EDGAR filing, "
            "sliced from the M1 adapter's canonical normalization (attest.ingest.edgar). "
            "Rebuild: python scripts/build_toy_corpus.py"
        ),
        "schema_version": "0.1.0",
        "source": FILING,
        "retrieved_with_user_agent_format": "name contact-email (SEC EDGAR fair-access policy)",
        "excerpt_count": len(excerpts),
        "excerpts": excerpts,
    }
    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nOK — {len(excerpts)} excerpts; manifest at {manifest_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
