#!/usr/bin/env python3
"""Fetch a patent's drawing sheets into its engagement store (RT-4 ingestion span).

Patents are read through their drawings — the reference numerals claims turn on live
in the figures. This downloads the drawing-page images from Google Patents' public
image storage and writes a hashed manifest next to them, so the figures view
(`scripts/patent_figures_view.py`) can render them alongside the parsed captions and
numeral legend (`attest.patents.parse_figures` / `reference_numerals`).

Locality (I3/I4): the images and manifest live UNDER the engagement store
(`corpus/engagements/<doc>/figures/`), which is gitignored — the engagement patent
stays local, never committed. Each image is sha256'd in the manifest (content
identity, the figure-side analogue of the text content-hash); a drawing is *displayed
evidence*, not a text citation (D21) — grounding still binds claims to the text.

    python scripts/fetch_patent_figures.py --doc US5447630A \
        --store corpus/engagements/US5447630A/store

By default the Google Patents HTML is fetched for the `--doc`; pass `--html PATH` to
parse a already-downloaded page (offline / reproducible). Deterministic given a fixed
page: sheets are ordered by page number and named `drawings-page-N.png`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"


def _get(url: str, *, binary: bool = False) -> bytes | str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https host)
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def drawing_urls(html: str, doc: str) -> dict[int, list[str]]:
    """The drawing-sheet PNG URLs per page. Google Patents serves each sheet at two
    storage paths — an 82×120 thumbnail and the full-resolution scan — under the same
    `…-drawings-page-N.png` name; both are returned so the caller can pick the
    full-res one (the larger download)."""
    stem = doc.rstrip("AB")                                # US5447630A → US5447630
    pat = re.compile(
        rf"https://patentimages\.storage\.googleapis\.com/[^\"']+?"
        rf"{re.escape(stem)}-drawings-page-(\d+)\.png"
    )
    by_page: dict[int, list[str]] = {}
    for m in pat.finditer(html):
        by_page.setdefault(int(m.group(1)), [])
        if m.group(0) not in by_page[int(m.group(1))]:
            by_page[int(m.group(1))].append(m.group(0))
    return dict(sorted(by_page.items()))


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch a patent's drawing sheets (RT-4)")
    ap.add_argument("--doc", required=True, help="document id, e.g. US5447630A")
    ap.add_argument("--store", required=True, help="engagement store dir (figures/ goes beside it)")
    ap.add_argument("--html", default=None, help="parse this saved Google Patents page")
    ap.add_argument("--source-url", default=None, help="override the Google Patents page URL")
    ns = ap.parse_args()

    out_dir = Path(ns.store).parent / "figures"
    src_url = ns.source_url or f"https://patents.google.com/patent/{ns.doc}/en"
    try:
        html = Path(ns.html).read_text(encoding="utf-8") if ns.html else _get(src_url)
    except Exception as e:                                  # noqa: BLE001 (surface + exit)
        print(f"error: could not read the patent page ({e})")
        return 1

    urls = drawing_urls(html, ns.doc)
    if not urls:
        print(f"no drawing sheets found for {ns.doc} at {src_url} — is the id right?")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    sheets = []
    for page, candidates in urls.items():
        name = f"drawings-page-{page}.png"
        best: tuple[bytes, str] | None = None              # keep the largest = full-res
        for url in candidates:
            try:
                blob = _get(url, binary=True)
            except Exception as e:                         # noqa: BLE001
                print(f"  ⚠ page {page}: download failed ({e})")
                continue
            if best is None or len(blob) > len(best[0]):
                best = (blob, url)
        if best is None:
            continue
        blob, url = best
        (out_dir / name).write_bytes(blob)
        sheets.append({
            "page": page, "file": name, "url": url,
            "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob),
        })
        print(f"  ✓ page {page:>2}  {name}  ({len(blob):,} bytes)")

    manifest = out_dir / "figures_manifest.json"
    manifest.write_text(json.dumps(
        {"doc": ns.doc, "source_url": src_url, "sheets": sheets}, indent=2) + "\n",
        encoding="utf-8")
    print(f"\nOK — {len(sheets)} sheet(s) + manifest under {out_dir} (local-only; gitignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
