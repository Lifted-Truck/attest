#!/usr/bin/env python3
"""Unguided label audit — what is ON the sheets that the manifest does NOT have (D29).

The text-guided confirmation pass (D28) can only look for labels the SPEC predicts on
a figure's sheet. Marks the text never recites — section/view letters, dimension
labels, unlabelled parts — are invisible to it by construction. This audit closes
that hole from the other side: sweep every sheet at high recall with EVERY available
engine, and report tokens the frozen manifest lacks.

**The acceptance rule is corroboration, not prediction.** An unguided high-recall
sweep hallucinates (tiles read leader lines as glyphs), so a candidate is only
*promotable* when independent engines agree on the same token at the same spot —
which is precisely the evidence D29 showed the engines can supply, since their blind
spots are disjoint. Single-engine candidates are REPORTED, never auto-promoted: they
go to a human, who is the only one entitled to say "yes, that mark is there."

Read-only: prints a report and (with --json) writes candidates for review. It never
edits the manifest — promotion is a deliberate act (`--promote` on the OCR script,
or a manual annotation), so the frozen-at-ingestion contract (D28/I6) is untouched.

    python scripts/audit_sheet_labels.py --store corpus/engagements/US5447630A/store
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path)
from ocr_patent_figures import (
    _RAPID_SINGLETON,
    ENGINE_READERS,
    TESSERACT_OK,
    VISION_OK,
    available_engines,
    marker_band_rescue,
)

from cairn.figures_map import load_manifest, merge_same_spot_numerals
from cairn.patents import NUMERAL_DIGITS

# What counts as a candidate LABEL on a drawing: a reference numeral (digits + an
# optional letter suffix), an acronym (STM/LTM/CPU/CL), or a lone view/section letter.
_LABEL = re.compile(
    rf"(?<![A-Za-z0-9])(\d{{1,{NUMERAL_DIGITS}}}[a-z]?|[A-Z]{{1,4}})(?![\da-z])")
_FURNITURE = re.compile(r"sheet\s+\d+\s+of\s+\d+|\b\d+\s+of\s+\d+\b|5[,\s]*447[,\s]*630|"
                        r"u\.?s\.?\s*patent|sep\.?\s*5|1995|FIGS?\b", re.IGNORECASE)
_PROSE = re.compile(r"[A-Za-z]{5,}")     # prose annotation, not a label
_HEADER_BAND = 0.88
_SAME_SPOT = 0.025


def sweep_page(path: Path, engines: list[str]) -> list[dict]:
    """Every label-shaped token any engine reads anywhere on the sheet (whole image
    + — for Vision — overlapping tiles + tesseract edge bands), merged by position
    so agreement across engines becomes an `engines` list."""
    found: list[dict] = []

    def take(obs: list[dict], engine: str) -> None:
        for o in obs:
            text = o["text"]
            if _FURNITURE.search(text) or _PROSE.search(text) or o["y"] >= _HEADER_BAND:
                continue
            for tok in _LABEL.findall(text):
                found.append({"numeral": tok.lower() if tok[0].isdigit() else tok,
                              "source_text": text, "confidence": o["confidence"],
                              "engine": engine, "x": o["x"], "y": o["y"],
                              "w": o.get("w", 0.0), "h": o.get("h", 0.0)})

    for eng in engines:
        take(ENGINE_READERS[eng](path), eng)
    if TESSERACT_OK:                       # edge bands: where section letters live
        for h in marker_band_rescue(path, {chr(c) for c in range(ord("A"), ord("Z") + 1)}):
            found.append({**h, "engine": "tesseract"})
    return merge_same_spot_numerals(found, radius=_SAME_SPOT)


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit sheets for labels the manifest lacks")
    ap.add_argument("--store", required=True)
    ap.add_argument("--pages", default="", help="comma list of page numbers (default: all)")
    ap.add_argument("--json", default="", help="write candidates here for review")
    ns = ap.parse_args()

    fig_dir = Path(ns.store).parent / "figures"
    manifest = load_manifest(ns.store)
    engines = available_engines()
    if "rapidocr" in engines and not _RAPID_SINGLETON:
        from ocr_patent_figures import RapidOCR
        _RAPID_SINGLETON.append(RapidOCR())
    print(f"engines: {', '.join(engines)}"
          f"{'  (+ tesseract edge bands)' if TESSERACT_OK else ''}"
          f"{'' if VISION_OK else '  [no Vision on this platform]'}\n")

    want = {int(p) for p in ns.pages.split(",") if p.strip()} or None
    out, promotable = [], 0
    for page in manifest["pages"]:
        if want and page["page"] not in want:
            continue
        have_tokens = {n["numeral"] for n in page["numerals"]}
        news = []
        for c in sweep_page(fig_dir / page["file"], engines):
            near = any(c["numeral"] == n["numeral"]
                       and abs(c["x"] - n["x"]) < _SAME_SPOT
                       and abs(c["y"] - n["y"]) < _SAME_SPOT for n in page["numerals"])
            if not near:
                c["new_token"] = c["numeral"] not in have_tokens
                news.append(c)
        if news:
            print(f"── p.{page['page']} ({page['file']}) — {len(news)} candidate(s) "
                  f"not in the manifest")
            for c in sorted(news, key=lambda d: (-len(d["engines"]), d["numeral"])):
                corr = len(c["engines"]) > 1
                promotable += corr
                tag = "✔ CORROBORATED" if corr else "· single-engine"
                new = " NEW-TOKEN" if c["new_token"] else ""
                print(f"   {tag}{new}  {c['numeral']!r:8} ({c['x']:.3f},{c['y']:.3f}) "
                      f"conf {c['confidence']:<5} {'+'.join(c['engines'])}  "
                      f"src={c['source_text']!r}")
            out.extend({**c, "page": page["page"]} for c in news)
    print(f"\n{len(out)} candidate(s) total · {promotable} corroborated by >1 engine "
          f"(promotable) · {len(out) - promotable} single-engine (human review)")
    if ns.json:
        Path(ns.json).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {ns.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
