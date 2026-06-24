#!/usr/bin/env python3
"""Build the M0 toy corpus (ROADMAP M0-T2) from a single SEC EDGAR filing.

Scope (brief §2): a tiny doc set of 5-10 verbatim excerpts to clear the audition
rig, NOT the real ingestion adapter (that is M1, where canonical normalization
and content-hashing live). This is a throwaway-grade fixture: it stores excerpts
*verbatim* with provenance, but the HTML->text conversion here is deliberately
simple and is NOT the canonical normalization M1 will define.

Deterministic and offline-after-first-run: the raw filing is cached under
data/raw/ (gitignored); re-runs read the cache so we don't re-hit EDGAR.

Usage:
    python scripts/build_toy_corpus.py            # build from cache or fetch
    SEC_USER_AGENT="you you@example.com" python scripts/build_toy_corpus.py
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "corpus" / "toy"

# Provenance for the single v1 reference filing (mirrors golden_seed.json corpus block).
DOC = {
    "doc_key": "AAPL-10K-FY2024",
    "company": "Apple Inc.",
    "ticker": "AAPL",
    "cik": "0000320193",
    "form": "10-K",
    "period_of_report": "2024-09-28",
    "accession": "0000320193-24-000123",
    "primary_document": "aapl-20240928.htm",
    "index_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123-index.htm",
    "primary_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm",
}

SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "ATTEST research contact@example.com")

# Each excerpt is sliced [start_anchor .. end_anchor). end_anchor is the first
# occurrence at/after the start. Anchors chosen for legibility, not cleverness.
SECTIONS = [
    {
        "key": "01_cover",
        "title": "Cover page (period of report)",
        "start": "UNITED STATES",
        "end": "PART I\n",
        "covers": ["G010"],
    },
    {
        "key": "02_statements_of_operations",
        "title": "Consolidated Statements of Operations",
        "start": "CONSOLIDATED STATEMENTS OF OPERATIONS",
        "end": "See accompanying Notes to Consolidated Financial Statements.",
        "covers": ["distractor"],
    },
    {
        "key": "03_balance_sheets",
        "title": "Consolidated Balance Sheets",
        "start": "CONSOLIDATED BALANCE SHEETS",
        "end": "See accompanying Notes to Consolidated Financial Statements.",
        "covers": ["G001-G008", "G016-G020"],
    },
    {
        "key": "04_statements_of_cash_flows",
        "title": "Consolidated Statements of Cash Flows",
        "start": "CONSOLIDATED STATEMENTS OF CASH FLOWS",
        "end": "See accompanying Notes to Consolidated Financial Statements.",
        "covers": ["distractor"],
    },
    {
        "key": "05_auditor_report",
        "title": "Report of Independent Registered Public Accounting Firm (financial statements)",
        "start": "Report of Independent Registered Public Accounting Firm",
        # Terminate at the *second* report header (internal control over financial reporting).
        "end": "To the Shareholders and the Board of Directors of Apple Inc.",
        "end_after": "/s/ Ernst & Young LLP",
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


class _TextExtractor(HTMLParser):
    """Minimal, dependency-free HTML -> text. Preserves visible words verbatim."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in ("p", "div", "tr", "br", "table", "h1", "h2", "h3", "li"):
            self.parts.append("\n")
        if tag == "td":
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        if tag in ("p", "div", "tr", "table"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(raw_html: str) -> str:
    p = _TextExtractor()
    p.feed(raw_html)
    txt = html_mod.unescape("".join(p.parts))
    # Normalize Unicode spaces (NBSP, thin, narrow-NBSP) to ASCII — content-preserving.
    txt = txt.translate({0xA0: " ", 0x2009: " ", 0x202F: " ", 0x2007: " "})
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n[ \t]+", "\n", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt


def fetch_raw() -> str:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache = RAW_DIR / DOC["primary_document"]
    if cache.exists():
        print(f"[cache] {cache.relative_to(ROOT)}")
        return cache.read_text(encoding="utf-8")
    print(f"[fetch] {DOC['primary_url']}")
    req = urllib.request.Request(DOC["primary_url"], headers={"User-Agent": SEC_USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (trusted SEC host)
        raw = resp.read().decode("utf-8")
    cache.write_text(raw, encoding="utf-8")
    return raw


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
    else:
        # Statements: keep the terminating "See accompanying Notes" line in the excerpt.
        if sec["end"].startswith("See accompanying"):
            end += len(sec["end"])
    return text[start:end].strip() + "\n"


def main() -> int:
    raw = fetch_raw()
    text = html_to_text(raw)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc_dir = OUT_DIR / DOC["doc_key"]
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
                "excerpt_id": f"{DOC['doc_key']}::{sec['key']}",
                "section_title": sec["title"],
                "path": str((doc_dir / fname).relative_to(ROOT)),
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
            "M0 toy corpus (ROADMAP M0-T2). Verbatim excerpts from a single EDGAR filing "
            "with provenance. HTML->text conversion here is throwaway-grade; canonical "
            "normalization + content-hashing is M1 (ingestion adapter). Rebuild: "
            "python scripts/build_toy_corpus.py"
        ),
        "schema_version": "0.1.0",
        "source": DOC,
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
