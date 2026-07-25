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
import shutil
import subprocess
from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path for the --confirm pass)

# Engine imports are OPTIONAL — ATTEST ingests on non-Mac systems too (D29):
# Vision is darwin-only; RapidOCR is a pip extra; Tesseract is a system binary.
try:
    import Quartz
    import Vision
    VISION_OK = True
except Exception:                                       # non-darwin / no pyobjc
    Quartz = Vision = None
    VISION_OK = False
try:
    from rapidocr_onnxruntime import RapidOCR
    RAPID_OK = True
except Exception:
    RapidOCR = None
    RAPID_OK = False
TESSERACT_OK = shutil.which("tesseract") is not None


def _pkg_version(name: str) -> str | None:
    """Installed version of a pip package (the module often has no __version__)."""
    import importlib.metadata as md
    try:
        return md.version(name)
    except Exception:
        return None

_FIG_LABEL = re.compile(r"FIGS?\.?\s*(\d+[A-Z]?)", re.IGNORECASE)
_SHEET_ID = re.compile(r"Sheet\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE)
# A reference LABEL: digits + an optional single letter suffix ("12a" is a distinct
# part from "12" — dropping the suffix reports 12 present and 12a missing, both wrong).
# Still letter-PREFIX rejected: "D1"/"D6" are FIG. 6's DIMENSION labels, not numerals.
_DIGIT_RUN = re.compile(r"(?<![A-Za-z0-9])(\d{1,3}[a-z]?)(?![\da-z])")
# Header furniture that must not yield numeral candidates (patent number, dates).
_HEADER_BAND = 0.88          # normalized y above this = the running header band
# Page/patent furniture whose digits are NOT reference numerals — the first pass
# drops these via the header BAND, but the tiled confirmation pass reads tiles with
# no absolute-y context, so it also string-matches these ("Sheet 1 of 8" boxed the
# header when searching for reference 1/8; "N of 8" is the page count).
_FURNITURE = re.compile(r"sheet\s+\d+\s+of\s+\d+|\b\d+\s+of\s+\d+\b|5[,\s]*447[,\s]*630",
                        re.IGNORECASE)
# A digit inside PROSE ("FINAL PURIFIED EFFLUENT. 1") is annotation text, not a
# reference numeral — real numeral reads are short ("14 140", "-82"), never carry
# multi-letter words.
_PROSE = re.compile(r"[A-Za-z]{4,}")


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


def obs_tesseract(path: Path) -> list[dict]:
    """Tesseract sparse-text pass (`--psm 11`) → common observations. A system
    binary, cross-platform — and empirically complementary to Vision (it reads the
    isolated view-marker glyphs and 14a/64 that Vision drops on this corpus)."""
    from PIL import Image

    from attest.figures_map import tesseract_tsv_to_observations
    w, h = Image.open(path).size
    r = subprocess.run(["tesseract", str(path), "stdout", "--psm", "11", "tsv"],
                       capture_output=True)
    return tesseract_tsv_to_observations(r.stdout.decode("utf-8", "replace"), w, h)


def obs_rapidocr(path: Path) -> list[dict]:
    """RapidOCR (PaddleOCR models on ONNX runtime — pip-only, cross-platform, no
    torch). Best whole-image recall of the three on patent sheets (24/30 labels on
    FIG 2 vs Vision's ~18). 1-bit scans must be widened to RGB first."""
    import numpy as np
    from PIL import Image

    from attest.figures_map import rapidocr_result_to_observations
    img = Image.open(path).convert("RGB")
    result, _ = _RAPID_SINGLETON[0](np.array(img))
    return rapidocr_result_to_observations(result, img.size[0], img.size[1])


_RAPID_SINGLETON: list = []          # model load is slow; init once in main()

ENGINE_READERS = {
    "vision": (lambda path: ocr_image(path)),
    "tesseract": obs_tesseract,
    "rapidocr": obs_rapidocr,
}


def available_engines() -> list[str]:
    out = []
    if VISION_OK:
        out.append("vision")
    if TESSERACT_OK:
        out.append("tesseract")
    if RAPID_OK:
        out.append("rapidocr")
    return out


_SAME_SPOT = 0.02        # normalized distance under which two reads are one instance


def tiled_search(path: Path, targets: set[str], *, rows: int = 4, cols: int = 2,
                 overlap: float = 0.12, reserved: set[str] | None = None) -> list[dict]:
    """Text-GUIDED confirmation: re-OCR a sheet in overlapping full-resolution tiles
    (which recovers small numerals the single-pass whole-image OCR drops on sparse
    line drawings) and return ONLY sightings of the requested `targets`. Restricting
    to text-predicted labels is what keeps the higher-recall pass from adding tiling
    noise (page/patent-number fragments). Bboxes are mapped back to full-image
    normalized coords (origin bottom-left) so the confirmation box still lands right.

    **Every instance is kept, not just the best one:** the same label legitimately
    appears more than once on a sheet (FIG. 3A carries "12a" twice), and a reviewer
    needs a box on each. Reads from OVERLAPPING tiles that land on the same spot are
    the same instance and collapse to the highest-confidence one.
    """
    cg = _load_cg(path)
    W, H = Quartz.CGImageGetWidth(cg), Quartz.CGImageGetHeight(cg)
    found: list[dict] = []
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
                    text = cand.string()
                    if _FURNITURE.search(text):          # "Sheet N of M", patent number
                        continue
                    if _FIG_LABEL.search(text):          # "FIG.4"'s own digits ≠ numeral 4
                        continue
                    # numeric labels come from the digit-run pattern; acronym labels
                    # ("STM") are matched whole-word; a SINGLE-letter view marker ("A")
                    # only as an exact token (a lone letter is too noisy as a substring);
                    # and a target like "14a" also matches its a↔0 OCR confusion "140"
                    # — Vision reads the suffix 'a' as '0' — but ONLY when "140" is not
                    # itself a known label (the `reserved` gate).
                    # NOTE: single-letter view markers are deliberately NOT matched
                    # here. Tiles amplify hallucination on line art (a curly leader
                    # read as "C!"), and a lone letter has no redundancy to check —
                    # letters come only from whole-image observations
                    # (_letters_from_first_pass), where the detector has layout
                    # context. Empirically: every real letter (B) was in the first
                    # pass; every tile-only letter was fake.
                    toks = ([] if _PROSE.search(text)
                            else [t.lower() for t in _DIGIT_RUN.findall(text)])
                    toks += [a for a in targets if len(a) > 1
                             and not a[0].isdigit() and re.search(rf"\b{re.escape(a)}\b", text)]
                    confusion = {t[:-1] + "0": t for t in targets
                                 if t.endswith("a") and t[:-1].isdigit()
                                 and t[:-1] + "0" not in (reserved or set())}
                    toks += [confusion[t] for t in toks if t in confusion]
                    for num in toks:
                        num = confusion.get(num, num)    # record under the TRUE label
                        if num not in targets:
                            continue
                        bb = obs.boundingBox()       # normalized within the TILE
                        # The tile rect (x, y) is TOP-left origin (Quartz sub-image),
                        # but Vision's bbox origin is BOTTOM-left within the tile — so x
                        # composes directly while y must be flipped back to the full
                        # image's bottom-left frame (else the box lands mirrored).
                        by = float(bb.origin.y)
                        y_full = round(1 - (y + h * (1 - by)) / H, 4)
                        if y_full >= _HEADER_BAND:       # the running header strip
                            continue
                        x_full = round((x + float(bb.origin.x) * w) / W, 4)
                        conf = round(float(cand.confidence()), 3)
                        hit = {
                            "numeral": num, "source_text": text, "confidence": conf,
                            "method": "text-guided", "engine": "vision",
                            "x": x_full, "y": y_full,
                            "w": round(float(bb.size.width) * w / W, 4),
                            "h": round(float(bb.size.height) * h / H, 4),
                        }
                        dup = next(
                            (o for o in found if o["numeral"] == num
                             and abs(o["x"] - x_full) < _SAME_SPOT
                             and abs(o["y"] - y_full) < _SAME_SPOT), None)
                        if dup is None:                  # a genuinely separate instance
                            found.append(hit)
                        elif conf > dup["confidence"]:   # same spot, better read
                            found[found.index(dup)] = hit
    return sorted(found, key=lambda d: (d["numeral"], -d["y"]))


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
        if _PROSE.search(o["text"]):             # prose annotation, not a numeral read
            continue
        for run in _DIGIT_RUN.findall(o["text"]):
            numerals.append({
                "numeral": run.lower(), "source_text": o["text"],
                "confidence": o["confidence"], "method": "first-pass",
                "engine": o.get("engine", "vision"),
                # full normalized bbox (origin bottom-left) — carried through so the
                # figures view can draw a confirmation box around the located numeral.
                "x": o["x"], "y": o["y"], "w": o["w"], "h": o["h"],
            })
    from attest.figures_map import merge_same_spot_numerals
    best_fig: dict[str, dict] = {}
    for fg in figs:                              # engines re-read the same FIG label
        if fg["fig"] not in best_fig or fg["confidence"] > best_fig[fg["fig"]]["confidence"]:
            best_fig[fg["fig"]] = fg
    return {"fig_labels": sorted(best_fig.values(), key=lambda f: f["fig"]),
            "sheet_id": sheet_id,
            "numerals": merge_same_spot_numerals(numerals)}




def marker_band_rescue(path: Path, letters: set[str]) -> list[dict]:
    """View-marker rescue via Tesseract sparse mode on the sheet's EDGE BANDS —
    markers sit at the edges by convention (they mark viewing directions from
    outside the object). Empirical basis: the FIG-2 "A" that Vision cannot detect
    by any API reads cleanly in a tesseract --psm 11 pass over the right band.
    Exact-token acceptance only (a lone letter is too noisy as a substring)."""
    from PIL import Image

    from attest.figures_map import tesseract_tsv_to_observations
    img = Image.open(path)
    W, H = img.size
    bands = {"left": (0, 0, int(0.20 * W), H), "right": (int(0.80 * W), 0, W, H),
             "top": (0, 0, W, int(0.18 * H)), "bottom": (0, int(0.82 * H), W, H)}
    hits = []
    for name, (x0, y0, x1, y1) in bands.items():
        tmp = path.parent / f".band_{name}.png"
        img.crop((x0, y0, x1, y1)).save(tmp)
        r = subprocess.run(["tesseract", str(tmp), "stdout", "--psm", "11", "tsv"],
                           capture_output=True)
        obs = tesseract_tsv_to_observations(
            r.stdout.decode("utf-8", "replace"), x1 - x0, y1 - y0)
        tmp.unlink(missing_ok=True)
        for o in obs:
            core = re.sub(r"[^A-Za-z0-9]", "", o["text"])
            if core not in letters:
                continue
            # band-local normalized bbox → full-image (both bottom-left origin)
            fx = (x0 + o["x"] * (x1 - x0)) / W
            f_top = (y0 + (1 - o["y"] - o["h"]) * (y1 - y0)) / H
            fw, fh = o["w"] * (x1 - x0) / W, o["h"] * (y1 - y0) / H
            fy = 1 - f_top - fh
            if fy >= _HEADER_BAND:
                continue
            hits.append({"numeral": core, "source_text": o["text"],
                         "confidence": o["confidence"], "method": "text-guided",
                         "engine": "tesseract", "x": round(fx, 4), "y": round(fy, 4),
                         "w": round(fw, 4), "h": round(fh, 4)})
    return hits


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
        drop_fragment_hits,
        fig_to_sheets,
        is_fragment,
        letters_from_first_pass,
        numeral_figures,
        numeral_sightings,
        numeral_text_figures,
    )
    from attest.ingest import DocumentStore
    from attest.patents import (
        acronym_labels,
        figure_references,
        numeral_key,
        parse_figures,
        reference_numerals,
    )
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
    want_per_page: dict[int, set[str]] = {}
    from attest.figures_map import sub_figure_parent, view_marker_letters
    labels = [n.number for n in reference_numerals(text)] + acronym_labels(text)
    reserved = set(labels)                                # gates the a↔0 confusion match
    markers = view_marker_letters(known)
    for lbl in labels:
        for fig in numeral_text_figures(text, lbl, refs):
            page = fig_to_page.get(fig)
            if page is not None and fig not in ocr_figs.get(lbl, []):
                want_per_page.setdefault(page, set()).add(lbl)
    marker_page: dict[str, int] = {}
    if markers:
        # A view marker sits ON THE PARENT figure (the one the views are taken of —
        # "views …of FIG. 2"), derived from the family's caption. Searching only the
        # parent's sheet is what structurally prevents tile hallucinations elsewhere
        # (a curly leader on FIG 6 once read as "C!"). No parent derivable → the
        # marker has no predicted location and is searched nowhere, not everywhere.
        already = {(s.numeral, s.page) for s in numeral_sightings(manifest)}
        for mk in markers:
            fam = next((f for f in known if f.endswith(mk) and len(f) > 1), None)
            parent = sub_figure_parent(text, fam[:-1], refs) if fam else None
            page = fig_to_page.get(parent) if parent else None
            if page is not None:
                marker_page[mk] = page
                if (mk, page) not in already:
                    want_per_page.setdefault(page, set()).add(mk)

    recovered = 0
    for page, targets in sorted(want_per_page.items()):
        page_markers = [mk for mk, pg in marker_page.items() if pg == page] \
            if markers else []
        hits = letters_from_first_pass(page_of[page], page_markers)
        if VISION_OK:                                 # Vision-guided tiling (darwin)
            hits += tiled_search(fig_dir / page_of[page]["file"], targets,
                                 reserved=reserved)
            # finer-tile fallback for what the standard pass STILL missed: small
            # faint numerals ("64 —" on FIG 2) only resolve at 8x4 full-res tiles.
            still = targets - {h["numeral"] for h in hits}
            if still:
                hits += tiled_search(fig_dir / page_of[page]["file"], still,
                                     rows=8, cols=4, overlap=0.08, reserved=reserved)
        hits = drop_fragment_hits(hits)               # hits vs each other ("4" inside "84")
        hits = [h for h in hits if not is_fragment(h, page_of[page])]
        # view markers still missing → tesseract edge-band rescue (exact token; the
        # engines are COMPLEMENTARY: Vision reads B but is blind to A, tesseract the
        # reverse — D29's whole point)
        got_now = {h["numeral"] for h in hits} | {n["numeral"]
                                                  for n in page_of[page]["numerals"]}
        still_mk = {mk for mk in page_markers if mk not in got_now}
        if still_mk and TESSERACT_OK:
            hits += [h for h in marker_band_rescue(fig_dir / page_of[page]["file"],
                                                   still_mk)
                     if h["numeral"] in still_mk]
        for h in hits:                                # same provenance shape as first-pass
            h["engines"] = sorted({h.pop("engine", "unknown")})
        if hits:
            page_of[page]["numerals"].extend(hits)
            got = ", ".join(str(h["numeral"]) for h in hits)
            recovered += len(hits)
            print(f"  ↻ p.{page}: text-guided recovery → {got}  "
                  f"(of predicted {', '.join(sorted(targets, key=numeral_key))})")
    return recovered


def main() -> int:
    ap = argparse.ArgumentParser(description="OCR drawing sheets → hashed manifest (D28)")
    ap.add_argument("--store", required=True, help="engagement store (figures/ is beside it)")
    ap.add_argument("--doc", help="document id — enables the text-guided confirmation pass")
    ap.add_argument("--confirm", action="store_true",
                    help="text-guided recovery pass for spec-predicted misses (needs --doc)")
    ap.add_argument("--engines", default="auto",
                    help="comma list of vision,tesseract,rapidocr — or 'auto' (all available)")
    ns = ap.parse_args()

    engines = available_engines() if ns.engines == "auto" else [
        e.strip() for e in ns.engines.split(",") if e.strip()]
    bad = [e for e in engines if e not in ENGINE_READERS]
    missing = [e for e in engines if e not in available_engines()]
    if bad or missing:
        print(f"unavailable engine(s): {', '.join(bad + missing)} "
              f"(available here: {', '.join(available_engines()) or 'none'})")
        return 1
    if not engines:
        print("no OCR engine available — install tesseract, `pip install "
              "rapidocr-onnxruntime`, or run on macOS (Vision)")
        return 1
    if "rapidocr" in engines and not _RAPID_SINGLETON:
        _RAPID_SINGLETON.append(RapidOCR())
    print(f"engines: {', '.join(engines)}  (complementary recall — D29)")

    fig_dir = Path(ns.store).parent / "figures"
    sheets = sorted(fig_dir.glob("drawings-page-*.png"),
                    key=lambda p: int(re.search(r"page-(\d+)", p.name).group(1)))
    if not sheets:
        print(f"no drawing sheets under {fig_dir} — run fetch_patent_figures.py first")
        return 1

    pages = []
    for p in sheets:
        obs = []
        for eng in engines:
            for o in ENGINE_READERS[eng](p):
                o["engine"] = eng
                obs.append(o)
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
        "engines": engines,
        "engine_provenance": {
            "platform": platform.platform(),
            "macos": platform.mac_ver()[0] or None,
            "tesseract": (subprocess.run(["tesseract", "--version"], capture_output=True)
                          .stdout.decode("utf-8", "replace").split("\n")[0]
                          if "tesseract" in engines else None),
            "rapidocr": _pkg_version("rapidocr-onnxruntime") if "rapidocr" in engines else None,
        },
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
