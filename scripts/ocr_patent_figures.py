#!/usr/bin/env python3
"""OCR a patent's drawing sheets → a hashed numeral-location manifest (RT-4/PE-2).

Reads the fetched drawing sheets (`scripts/fetch_patent_figures.py`) with Apple's
Vision framework (pre-trained, on-device, no network) and writes
`figures/ocr_manifest.json`: per sheet, every text observation with its confidence
and position, plus the extracted FIG labels, the sheet's own "Sheet N of M"
self-identification, and normalized numeral candidates.

**Where this sits in the architecture (D28):** OCR is an **ingestion-time** step —
run once per engagement, output hashed and frozen, exactly like the corpus
content-hash (I3's pattern). Nothing at runtime calls OCR: the evidence path stays
deterministic *over the manifest* (`attest.figures_map`). Vision's output could
change across macOS versions — that is why the manifest is frozen at ingestion,
not recomputed.

**The honesty story (Julian's condition for adopting OCR):** OCR is strong but not
100% — leader lines fuse with digits ("10 -" → conf 0.3), rotated text garbles.
Every observation carries Vision's confidence; every derived numeral keeps its raw
source text; the manifest records the OS/Vision provenance; and downstream
surfaces are required to render OCR-derived facts as *located by OCR (conf N)*,
never as verified text citations (D21: a drawing is displayed evidence).

Local-only: sheets + manifest live under the gitignored engagement store.

    python scripts/ocr_patent_figures.py --store corpus/engagements/US5447630A/store
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
from pathlib import Path

import Quartz
import Vision

_FIG_LABEL = re.compile(r"FIGS?\.?\s*(\d+[A-Z]?)", re.IGNORECASE)
_SHEET_ID = re.compile(r"Sheet\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE)
# A digit run NOT letter-prefixed: "D1"/"D6" are FIG. 6's DIMENSION labels, not
# reference numerals — without the lookbehind they polluted the numeral set as 1..6.
_DIGIT_RUN = re.compile(r"(?<![A-Za-z0-9])\d{1,3}(?!\d)")
# Header furniture that must not yield numeral candidates (patent number, dates).
_HEADER_BAND = 0.88          # normalized y above this = the running header band


def ocr_image(path: Path) -> list[dict]:
    url = Quartz.CFURLCreateWithFileSystemPath(
        None, str(path), Quartz.kCFURLPOSIXPathStyle, False)
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)        # digits + labels, not prose
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(f"Vision OCR failed on {path.name}: {err}")
    out = []
    for obs in (req.results() or []):
        cand = obs.topCandidates_(1)[0]
        bb = obs.boundingBox()                   # normalized, origin bottom-left
        out.append({
            "text": cand.string(),
            "confidence": round(float(cand.confidence()), 3),
            "x": round(float(bb.origin.x), 4), "y": round(float(bb.origin.y), 4),
            "w": round(float(bb.size.width), 4), "h": round(float(bb.size.height), 4),
        })
    return out


def derive(observations: list[dict]) -> dict:
    """Deterministic extraction over raw observations: FIG labels, sheet self-id,
    numeral candidates (digit runs outside the header band, with provenance)."""
    figs, sheet_id, numerals = [], None, []
    for o in observations:
        m = _SHEET_ID.search(o["text"])
        if m:
            sheet_id = {"sheet": int(m.group(1)), "of": int(m.group(2))}
        for m in _FIG_LABEL.finditer(o["text"]):
            figs.append({"fig": m.group(1).upper(), "confidence": o["confidence"],
                         "x": o["x"], "y": o["y"]})
        if o["y"] >= _HEADER_BAND:               # header: patent no., date — not numerals
            continue
        if _FIG_LABEL.search(o["text"]):         # a FIG label's digits are not numerals
            continue
        for run in _DIGIT_RUN.findall(o["text"]):
            numerals.append({
                "numeral": int(run), "source_text": o["text"],
                "confidence": o["confidence"],
                # full normalized bbox (origin bottom-left) — carried through so the
                # figures view can draw a confirmation box around the located numeral.
                "x": o["x"], "y": o["y"], "w": o["w"], "h": o["h"],
            })
    return {"fig_labels": figs, "sheet_id": sheet_id, "numerals": numerals}


def main() -> int:
    ap = argparse.ArgumentParser(description="OCR drawing sheets → hashed manifest (D28)")
    ap.add_argument("--store", required=True, help="engagement store (figures/ is beside it)")
    ns = ap.parse_args()

    fig_dir = Path(ns.store).parent / "figures"
    sheets = sorted(fig_dir.glob("drawings-page-*.png"),
                    key=lambda p: int(re.search(r"page-(\d+)", p.name).group(1)))
    if not sheets:
        print(f"no drawing sheets under {fig_dir} — run fetch_patent_figures.py first")
        return 1

    pages = []
    for p in sheets:
        obs = ocr_image(p)
        d = derive(obs)
        pages.append({
            "file": p.name,
            "page": int(re.search(r"page-(\d+)", p.name).group(1)),
            "image_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            **d, "observations": obs,
        })
        figs = ",".join(f["fig"] for f in d["fig_labels"]) or "—"
        sid = d["sheet_id"] or {}
        print(f"  ✓ {p.name}: FIG {figs} · sheet {sid.get('sheet','?')}/{sid.get('of','?')} "
              f"· {len(d['numerals'])} numeral candidates · {len(obs)} observations")

    manifest = {
        "engine": "apple-vision",
        "engine_provenance": {"macos": platform.mac_ver()[0], "machine": platform.machine()},
        "warning": ("OCR-derived: strong but not 100% reliable (leader lines fuse with "
                    "digits; rotated text garbles). Confidence per observation; frozen at "
                    "ingestion — downstream is deterministic over THIS file, never re-OCRed "
                    "at runtime (D28). A drawing is displayed evidence, not a citation (D21)."),
        "pages": pages,
    }
    blob = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True)
    out = fig_dir / "ocr_manifest.json"
    out.write_text(blob + "\n", encoding="utf-8")
    print(f"\nOK — {out}  (sha256 {hashlib.sha256(blob.encode()).hexdigest()[:16]}…, "
          f"{len(pages)} sheets; local-only/gitignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
