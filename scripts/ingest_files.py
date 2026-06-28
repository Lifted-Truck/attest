#!/usr/bin/env python3
"""Ingest your own plain-text files into an ATTEST document store (corpus-agnostic).

The generic counterpart to `ingest_corpus.py` (which is EDGAR-specific). Use it to
stand up a new engagement's corpus, then point `ATTEST_STORE` (in `.mcp.json`) at it.

Usage:
    python scripts/ingest_files.py patent.txt --store corpus/acme/store
    python scripts/ingest_files.py ~/matter/*.txt --store corpus/acme/store --kind patent
    python scripts/ingest_files.py ~/matter/docs/   --store corpus/acme/store   # a folder

Plain text only (.txt/.md). HTML/PDF/patent-XML need a corpus adapter (PE-1).
"""

from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from attest.ingest.files import ingest_paths


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest plain-text files into an ATTEST store")
    ap.add_argument("paths", nargs="+", help="files or a folder of .txt/.md")
    ap.add_argument("--store", required=True, help="target store dir (keep engagements separate)")
    ap.add_argument("--kind", default=None, help="optional metadata tag (e.g. 'patent')")
    ns = ap.parse_args()

    try:
        docs = ingest_paths(ns.paths, ns.store, kind=ns.kind)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}")
        return 1
    if not docs:
        print("Nothing ingested — no .txt/.md files found in the given paths.")
        return 1

    for d in docs:
        print(f"  {d.doc_id:<24} {len(d):>8} chars  sha256={d.content_hash[:12]}…")
    print(f"\nOK — {len(docs)} document(s) in {ns.store}  "
          f"(set ATTEST_STORE={ns.store} to use it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
