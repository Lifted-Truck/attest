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

import _bootstrap  # noqa: F401  (puts src/ on sys.path for the --confirm pass)
import Quartz
import Vision

_FIG_LABEL = re.compile(r"FIGS?\.?\s*(\d+[A-Z]?)", re.IGNORECASE)
_SHEET_ID = re.compile(r"Sheet\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE)
# A digit run NOT letter-prefixed: "D1"/"D6" are FIG. 6's DIMENSION labels, not
# reference numerals — without the lookbehind they polluted the numeral set as 1..6.
_DIGIT_RUN = re.compile(r"(?<![A-Za-z0-9])\d{1,3}(?!\d)")
# Header furniture that must not yield numeral candidates (patent number, dates).
_HEADER_BAND = 0.88          # normalized y above this = the running header band


def _load_cg(path: Path):
    url = Quartz.CFURLCreateWithFileSystemPath(
        None, str(path), Quartz.kCFURLPOSIXPathStyle, False)
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    return Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)


def _recognize(cg, *, n_candidates: int = 1, min_height: float = 0.0) -> list:
    """Raw Vision text observations for a CGImage. `topCandidates_(n)` and a lowered
    `minimumTextHeight` are the recall knobs the text-guided pass turns up."""
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)        # digits + labels, not prose
    if min_height:
        req.setMinimumTextHeight_(min_height)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(f"Vision OCR failed: {err}")
    return list(req.results() or []), n_candidates


def ocr_image(path: Path) -> list[dict]:
    results, _ = _recognize(_load_cg(path))
    out = []
    for obs in results:
        cand = obs.topCandidates_(1)[0]
        bb = obs.boundingBox()                   # normalized, origin bottom-left
        out.append({
            "text": cand.string(),
            "confidence": round(float(cand.confidence()), 3),
            "x": round(float(bb.origin.x), 4), "y": round(float(bb.origin.y), 4),
            "w": round(float(bb.size.width), 4), "h": round(float(bb.size.height), 4),
        })
    return out


def tiled_search(path: Path, targets: set[int], *, rows: int = 4, cols: int = 2,
                 overlap: float = 0.12) -> list[dict]:
    """Text-GUIDED confirmation: re-OCR a sheet in overlapping full-resolution tiles
    (which recovers small numerals the single-pass whole-image OCR drops on sparse
    line drawings) and return ONLY sightings of the requested `targets`. Restricting
    to text-predicted numerals is what keeps the higher-recall pass from adding tiling
    noise (page/patent-number fragments). Bboxes are mapped back to full-image
    normalized coords (origin bottom-left) so the confirmation box still lands right.
    """
    cg = _load_cg(path)
    W, H = Quartz.CGImageGetWidth(cg), Quartz.CGImageGetHeight(cg)
    best: dict[int, dict] = {}
    for r in range(rows):
        for c in range(cols):
            x = max(0, int(c * W / cols - overlap * W))
            y = max(0, int(r * H / rows - overlap * H))
            w = min(W - x, int(W / cols + 2 * overlap * W))
            h = min(H - y, int(H / rows + 2 * overlap * H))
            tile = Quartz.CGImageCreateWithImageInRect(cg, Quartz.CGRectMake(x, y, w, h))
            results, ncand = _recognize(tile, n_candidates=3)
            for obs in results:
                for cand in obs.topCandidates_(ncand):
                    for tok in _DIGIT_RUN.findall(cand.string()):
                        num = int(tok)
                        if num not in targets:
                            continue
                        conf = round(float(cand.confidence()), 3)
                        if num in best and best[num]["confidence"] >= conf:
                            continue
                        bb = obs.boundingBox()       # normalized within the TILE
                        # The tile rect (x, y) is TOP-left origin (Quartz sub-image),
                        # but Vision's bbox origin is BOTTOM-left within the tile — so x
                        # composes directly while y must be flipped back to the full
                        # image's bottom-left frame (else the box lands mirrored).
                        by = float(bb.origin.y)
                        best[num] = {
                            "numeral": num, "source_text": cand.string(), "confidence": conf,
                            "method": "text-guided",
                            "x": round((x + float(bb.origin.x) * w) / W, 4),
                            "y": round(1 - (y + h * (1 - by)) / H, 4),
                            "w": round(float(bb.size.width) * w / W, 4),
                            "h": round(float(bb.size.height) * h / H, 4),
                        }
    return [best[n] for n in sorted(best)]


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
                "confidence": o["confidence"], "method": "first-pass",
                # full normalized bbox (origin bottom-left) — carried through so the
                # figures view can draw a confirmation box around the located numeral.
                "x": o["x"], "y": o["y"], "w": o["w"], "h": o["h"],
            })
    return {"fig_labels": figs, "sheet_id": sheet_id, "numerals": numerals}


def confirm_pass(pages: list[dict], store: str, doc: str, fig_dir: Path) -> int:
    """Text-guided confirmation (the "push truth from all angles" pass): where the
    SPEC predicts a numeral on a figure's sheet but the first OCR pass missed it,
    re-OCR that sheet (tiled, higher recall) searching only for the predicted numeral,
    and add any recovery as a `text-guided` sighting. Returns the count recovered.

    An OCR miss and a genuine drawing omission are indistinguishable to the first pass
    (D28/D10); the text prediction resolves many of them — and any it CANNOT recover
    stays flagged, a stronger signal that it needs a human eye.
    """
    from attest.figures_map import (
        fig_to_sheets,
        numeral_figures,
        numeral_sightings,
        numeral_text_figures,
    )
    from attest.ingest import DocumentStore
    from attest.patents import figure_references, parse_figures, reference_numerals
    from attest.spans import SpanStore

    text = SpanStore.from_store(DocumentStore(store)).get_document(doc)
    refs = figure_references(text)
    manifest = {"pages": pages}                              # the shape figures_map reads
    known = sorted({f.number for f in parse_figures(text)} | {r.number for r in refs})
    assigns = fig_to_sheets(manifest, known)
    fig_to_page = {a.fig: a.page for a in assigns}
    page_of = {p["page"]: p for p in pages}
    ocr_figs = numeral_figures(assigns, numeral_sightings(manifest))

    # predicted: numeral → figures the spec discusses it near; keep those the first
    # pass did NOT already place on that figure's sheet.
    want_per_page: dict[int, set[int]] = {}
    for n in reference_numerals(text):
        for fig in numeral_text_figures(text, n.number, refs):
            page = fig_to_page.get(fig)
            if page is not None and fig not in ocr_figs.get(n.number, []):
                want_per_page.setdefault(page, set()).add(n.number)

    recovered = 0
    for page, targets in sorted(want_per_page.items()):
        hits = tiled_search(fig_dir / page_of[page]["file"], targets)
        if hits:
            page_of[page]["numerals"].extend(hits)
            got = ", ".join(str(h["numeral"]) for h in hits)
            recovered += len(hits)
            print(f"  ↻ p.{page}: text-guided recovery → {got}  "
                  f"(of predicted {', '.join(map(str, sorted(targets)))})")
    return recovered


def main() -> int:
    ap = argparse.ArgumentParser(description="OCR drawing sheets → hashed manifest (D28)")
    ap.add_argument("--store", required=True, help="engagement store (figures/ is beside it)")
    ap.add_argument("--doc", help="document id — enables the text-guided confirmation pass")
    ap.add_argument("--confirm", action="store_true",
                    help="text-guided recovery pass for spec-predicted misses (needs --doc)")
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

    recovered = 0
    if ns.confirm:
        if not ns.doc:
            print("--confirm needs --doc (to read the spec's numeral→figure predictions)")
            return 1
        print("\ntext-guided confirmation pass (spec predicts, tiled OCR confirms):")
        recovered = confirm_pass(pages, ns.store, ns.doc, fig_dir)
        print(f"  → recovered {recovered} spec-predicted numeral(s) the first pass missed")

    manifest = {
        "engine": "apple-vision",
        "engine_provenance": {"macos": platform.mac_ver()[0], "machine": platform.machine()},
        "warning": ("OCR-derived: strong but not 100% reliable (leader lines fuse with "
                    "digits; rotated text garbles). Confidence + method (first-pass / "
                    "text-guided) per numeral; frozen at ingestion — downstream is "
                    "deterministic over THIS file, never re-OCRed at runtime (D28). A "
                    "drawing is displayed evidence, not a citation (D21)."),
        "text_guided_recoveries": recovered,
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
