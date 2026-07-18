"""FIG→sheet and numeral→sheet mapping over the OCR manifest (RT-4/PE-2, D28).

The deterministic half of the OCR split: `scripts/ocr_patent_figures.py` runs
Apple-Vision OCR **once at ingestion** and freezes a hashed manifest; everything
here is a pure function over that manifest — same manifest, same answers (I6).
Nothing in this module (or anywhere at runtime) calls OCR.

Honesty rules (D21/D28), enforced in the data model:
- every mapping carries its **method** — `"ocr"` (a label read on the sheet) or
  `"elimination"` (exactly one known figure unassigned + exactly one sheet with a
  garbled/missing label) — and its OCR confidence where one exists;
- a numeral's sheet location is *"located by OCR"*, never a verified citation —
  the spec TEXT remains the only citable surface;
- cross-checks surface facts for review ("recited in the spec, not located on any
  sheet — OCR miss or drawing omission"), never conclusions (D10).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

OCR = "ocr"
ELIMINATION = "elimination"


@dataclass(frozen=True)
class SheetAssignment:
    fig: str                  # "1", "3A"
    page: int                 # drawings-page-N
    method: str               # OCR | ELIMINATION
    confidence: float | None  # Vision confidence of the label (None for elimination)


@dataclass(frozen=True)
class NumeralSighting:
    numeral: int
    page: int
    confidence: float
    source_text: str          # the raw OCR text the digits came from ("-82" → 82)


def load_manifest(store_dir: str | Path) -> dict:
    path = Path(store_dir).parent / "figures" / "ocr_manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def fig_to_sheets(manifest: dict, known_figs: list[str]) -> list[SheetAssignment]:
    """Assign each known figure (from the TEXT side — `patents.parse_figures` /
    `figure_references`) to its drawing sheet.

    Primary evidence: an OCR-read FIG label on the sheet, accepted only if it names
    a KNOWN figure (so a garbled "FIG.A" cannot invent figure A). Fallback: if
    exactly one known figure is unassigned and exactly one sheet has no accepted
    label, they pair by ELIMINATION — flagged as such, never silently. Anything
    less determinate stays unassigned (a surfaced gap, not a guess).
    """
    known = {f.upper() for f in known_figs}
    out: list[SheetAssignment] = []
    labeled_pages: set[int] = set()
    for page in manifest["pages"]:
        for lab in page["fig_labels"]:
            if lab["fig"] in known:
                out.append(SheetAssignment(lab["fig"], page["page"], OCR, lab["confidence"]))
                labeled_pages.add(page["page"])
    assigned = {a.fig for a in out}
    missing = sorted(known - assigned)
    unlabeled = [p["page"] for p in manifest["pages"] if p["page"] not in labeled_pages]
    if len(missing) == 1 and len(unlabeled) == 1:
        out.append(SheetAssignment(missing[0], unlabeled[0], ELIMINATION, None))
    return sorted(out, key=lambda a: (a.page, a.fig))


def numeral_sightings(manifest: dict, *, min_confidence: float = 0.0) -> list[NumeralSighting]:
    """Every numeral candidate OCR located on any sheet (optionally floored by
    confidence). Located-by-OCR facts — display/review evidence only."""
    out = [
        NumeralSighting(n["numeral"], page["page"], n["confidence"], n["source_text"])
        for page in manifest["pages"] for n in page["numerals"]
        if n["confidence"] >= min_confidence
    ]
    return sorted(out, key=lambda s: (s.page, s.numeral))


@dataclass(frozen=True)
class NumeralCrossCheck:
    matched: dict[int, list[NumeralSighting]]   # recited in spec AND located on sheets
    text_only: list[int]                        # recited, never located (OCR miss OR omission)
    sheet_only: list[NumeralSighting]           # located, never recited (OCR artifact OR gap)


def cross_check_numerals(
    text_numerals: list[int], manifest: dict, *, min_confidence: float = 0.0,
) -> NumeralCrossCheck:
    """The PE-2 element-numeral bridge: reconcile the spec's numeral list (from
    `patents.reference_numerals`, deterministic over text) with the sheets' (OCR).

    Surfaces three fact classes for professional review. `text_only` is worded as
    "not LOCATED on any sheet" — an OCR miss and a drawing omission are
    indistinguishable from here, and the check never claims otherwise (D10).
    """
    sightings = numeral_sightings(manifest, min_confidence=min_confidence)
    by_num: dict[int, list[NumeralSighting]] = {}
    for s in sightings:
        by_num.setdefault(s.numeral, []).append(s)
    text_set = set(text_numerals)
    return NumeralCrossCheck(
        matched={n: by_num[n] for n in sorted(text_set & set(by_num))},
        text_only=sorted(text_set - set(by_num)),
        sheet_only=[s for s in sightings if s.numeral not in text_set],
    )


def element_numeral_issues(
    numerals, manifest: dict, *, min_confidence: float = 0.0,
) -> list[dict]:
    """PE-2's element-numeral consistency check, at last buildable at high precision
    — the OCR manifest supplies the drawing-side ground truth the naive text-only
    heuristic lacked (it flagged 34/67 numerals, mostly false positives).

    `numerals` is `patents.reference_numerals(text)` output (number + element).
    Returns surfaced facts, one dict per issue, worded to D10 discipline: a
    structural observation with its OCR caveat, never a §112 conclusion.
    """
    cc = cross_check_numerals([n.number for n in numerals], manifest,
                              min_confidence=min_confidence)
    by_num = {n.number: n.element for n in numerals}
    issues = [
        {"kind": "recited-not-located", "numeral": n,
         "message": (f'numeral {n} ("{by_num[n]}") is recited in the specification but '
                     f"was not located on any drawing sheet — an OCR miss and a drawing "
                     f"omission are indistinguishable here; review the sheets")}
        for n in cc.text_only
    ]
    issues += [
        {"kind": "located-not-recited", "numeral": s.numeral,
         "message": (f"numeral {s.numeral} appears on sheet page {s.page} "
                     f'(OCR of "{s.source_text}", conf {s.confidence}) but is never '
                     f"recited in the specification — an OCR artefact and a spec gap "
                     f"are indistinguishable here; review")}
        for s in cc.sheet_only
    ]
    return issues
