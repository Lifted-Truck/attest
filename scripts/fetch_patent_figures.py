#!/usr/bin/env python3
"""Fetch a patent's drawing sheets into its engagement store (RT-4 ingestion span).

Patents are read through their drawings — the reference numerals claims turn on live
in the figures. This downloads the drawing-page images from Google Patents' public
image storage and writes a hashed manifest next to them, so the figures view
(`scripts/patent_figures_view.py`) can render them alongside the parsed captions and
numeral legend (`cairn.patents.parse_figures` / `reference_numerals`).

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
    # Strip the KIND CODE, which is a letter optionally followed by a digit: A, A1, B2…
    # `doc.rstrip("AB")` was fitted to US5447630A and silently does nothing to
    # US8046721B2, because "B2" ends with a digit — so the stem stayed "US8046721B2",
    # every URL pattern missed, and the fetch reported "no drawing sheets found" as if
    # the patent had none (RT-6 corpus 2).
    stem = re.sub(r"[A-Z]\d?$", "", doc)                  # US5447630A → US5447630
    host = r"https://patentimages\.storage\.googleapis\.com/[^\"']+?"
    # TWO naming schemes, and only knowing one of them is why this returned nothing for
    # US8046721B2 (RT-6's second corpus). Google Patents serves older grants as
    # `US5447630-drawings-page-2.png` and newer ones as
    # `US08046721-20111025-D00009.png` — an 8-digit ZERO-PADDED number, the grant date,
    # and a D-number. The zero-padding is the trap: a naive stem never matches.
    padded = f"US{int(stem.lstrip('US')):08d}" if stem.lstrip("US").isdigit() else stem
    patterns = [
        re.compile(rf"{host}{re.escape(stem)}-drawings-page-(\d+)\.png"),
        re.compile(rf"{host}{re.escape(padded)}-\d{{8}}-D(\d+)\.png"),
    ]
    by_page: dict[int, list[str]] = {}
    for pat in patterns:
        for m in pat.finditer(html):
            n = int(m.group(1))
            by_page.setdefault(n, [])
            if m.group(0) not in by_page[n]:
                by_page[n].append(m.group(0))
        if by_page:                    # first scheme that matches wins; never mix them
            break
    return dict(sorted(by_page.items()))


def geometry_report(out_dir: Path, sheets: list) -> list[str]:
    """Flag sheets whose pixel geometry disagrees with their siblings (D45).

    Self-calibrating, with no magic threshold: sheets of ONE grant are scanned together,
    so a sheet that differs materially from the median is a different RENDITION, not a
    different drawing. That is the signature of the substitution class — the 82x120
    thumbnail served under the full-res name (L0003), and here a 1497x1536 sheet among
    2112x3286 siblings on US8046721B2. Every downstream coordinate is a NORMALIZED
    fraction, so a rendition swap is invisible in the manifest by construction; this is
    the only place it can be seen.

    Reports rather than refuses: a genuinely odd sheet (a landscape fold-out) is legal,
    and this cannot tell the two apart. A human can.
    """
    from PIL import Image
    dims = []
    for s in sheets:
        f = out_dir / s["file"] if isinstance(s, dict) else out_dir / str(s)
        if not f.exists():
            continue
        with Image.open(f) as im:
            dims.append((f.name, im.size[0], im.size[1]))
    if len(dims) < 3:
        return []
    widths = sorted(d[1] for d in dims)
    heights = sorted(d[2] for d in dims)
    mw, mh = widths[len(widths) // 2], heights[len(heights) // 2]
    out = []
    for name, w, h in dims:
        if abs(w - mw) / mw > 0.15 or abs(h - mh) / mh > 0.15:
            out.append(f"  \u26a0 {name}: {w}x{h} vs median {mw}x{mh} — a different "
                       f"RENDITION, not a different drawing. Small isolated labels may "
                       f"be unreadable at this scale; re-fetch before trusting it.")
    return out


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
    for line in geometry_report(out_dir, sheets):
        print(line)
    print(f"\nOK — {len(sheets)} sheet(s) + manifest under {out_dir} (local-only; gitignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
