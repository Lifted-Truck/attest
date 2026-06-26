#!/usr/bin/env python3
"""Ingest the v1 reference corpus into the document store (ROADMAP M1-T1).

Fetches each registered EDGAR filing, normalizes it to canonical text, hashes it
at ingest (I3), and writes it to corpus/store/. Deterministic and offline after
the first run (raw HTML cached under gitignored data/raw/). The committed store
is what CI and the span store (M1-T2) read — no network needed in tests.

Usage:
    python scripts/ingest_corpus.py
    SEC_USER_AGENT="you you@example.com" python scripts/ingest_corpus.py
"""

from __future__ import annotations

from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from attest.ingest import DocumentStore
from attest.ingest.edgar import FILINGS, ingest

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
STORE_DIR = ROOT / "corpus" / "store"


def main() -> int:
    store = DocumentStore(STORE_DIR)
    for doc_id in FILINGS:
        doc = ingest(doc_id, RAW_DIR)
        store.write(doc)
        print(f"  {doc_id:<20} {len(doc):>7} chars  sha256={doc.content_hash[:12]}…")
    print(f"\nOK — {len(FILINGS)} document(s) in {STORE_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
