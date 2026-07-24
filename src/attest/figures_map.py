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
import re
from dataclasses import dataclass
from pathlib import Path

from .patents import numeral_key

OCR = "ocr"
ELIMINATION = "elimination"

# How far a figure's "current context" carries in the spec text. Patent prose says
# "Referring now to FIG. 2, …" and then discusses that figure's parts for several
# paragraphs, so a numeral's governing figure is the nearest PRECEDING FIG reference,
# not one within a tight radius. Measured on US5447630A: at 500 chars the check failed
# to tie 14a/54/62/64/66 to FIG. 2 (numerals the spec plainly discusses under it, and
# which a reviewer spotted on the sheet); at 2000 all five tie correctly. Wider than
# that ties more numerals without recovering any more of them — so 2000 is where the
# evidence stops improving.
FIGURE_CONTEXT_WINDOW = 2000


def label_pattern(label: str) -> str:
    """Regex for a reference LABEL as a standalone token. A numeric label needs
    number-aware guards (no trailing digit/letter so "12" never fires inside "12a";
    no decimal "10.5"; a trailing comma is punctuation unless it is grouping
    "10,500"). An acronym label ("STM") just needs word boundaries."""
    if label[0].isdigit():
        return rf"(?<![\d.,]){re.escape(label)}(?![\da-z])(?!\.\d)(?!,\d)"
    return rf"\b{re.escape(label)}\b" 


@dataclass(frozen=True)
class SheetAssignment:
    fig: str                  # "1", "3A"
    page: int                 # drawings-page-N
    method: str               # OCR | ELIMINATION
    confidence: float | None  # Vision confidence of the label (None for elimination)


@dataclass(frozen=True)
class NumeralSighting:
    numeral: str      # a reference LABEL: "12", "12a", or an acronym
    page: int
    confidence: float
    source_text: str          # the raw OCR text the digits came from ("-82" → 82)
    # (x, y, w, h) normalized, origin bottom-left — for the confirmation box overlay:
    bbox: tuple[float, float, float, float] | None = None
    method: str = "first-pass"  # "first-pass" | "text-guided" (D28 confirmation pass)


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
    out = []
    for page in manifest["pages"]:
        for n in page["numerals"]:
            if n["confidence"] < min_confidence:
                continue
            bbox = ((n["x"], n["y"], n["w"], n["h"])
                    if all(k in n for k in ("x", "y", "w", "h")) else None)
            out.append(NumeralSighting(n["numeral"], page["page"], n["confidence"],
                                       n["source_text"], bbox, n.get("method", "first-pass")))
    return sorted(out, key=lambda s: (s.page, numeral_key(s.numeral)))


def numeral_figures(
    assignments: list[SheetAssignment], sightings: list[NumeralSighting],
) -> dict[str, list[str]]:
    """For every numeral, ALL figures it is OCR-located in (a numeral shared across
    figures — "the separator 10" appears in FIGS. 1, 2, 5 — surfaces all of them,
    not just the first text mention). Figures are ordered as assigned; a sighting on
    an unassigned sheet contributes nothing (no figure to name). Locate-only."""
    page_to_fig = {a.page: a.fig for a in assignments}
    out: dict[str, list[str]] = {}
    for s in sightings:
        fig = page_to_fig.get(s.page)
        if fig and fig not in out.setdefault(s.numeral, []):
            out[s.numeral].append(fig)
    return {n: sorted(figs, key=lambda f: (len(f), f)) for n, figs in out.items()}


@dataclass(frozen=True)
class NumeralCrossCheck:
    matched: dict[str, list[NumeralSighting]]   # recited in spec AND located on sheets
    text_only: list[str]                        # recited, never located (OCR miss OR omission)
    sheet_only: list[NumeralSighting]           # located, never recited (OCR artifact OR gap)


def cross_check_numerals(
    text_numerals: list[str], manifest: dict, *, min_confidence: float = 0.0,
) -> NumeralCrossCheck:
    """The PE-2 element-numeral bridge: reconcile the spec's numeral list (from
    `patents.reference_numerals`, deterministic over text) with the sheets' (OCR).

    Surfaces three fact classes for professional review. `text_only` is worded as
    "not LOCATED on any sheet" — an OCR miss and a drawing omission are
    indistinguishable from here, and the check never claims otherwise (D10).
    """
    sightings = numeral_sightings(manifest, min_confidence=min_confidence)
    by_num: dict[str, list[NumeralSighting]] = {}
    for s in sightings:
        by_num.setdefault(s.numeral, []).append(s)
    text_set = set(text_numerals)
    return NumeralCrossCheck(
        matched={n: by_num[n] for n in sorted(text_set & set(by_num), key=numeral_key)},
        text_only=sorted(text_set - set(by_num), key=numeral_key),
        sheet_only=[s for s in sightings if s.numeral not in text_set],
    )


def relevant_figures(
    cited_span_texts: list[str],
    assignments: list[SheetAssignment],
    sightings: list[NumeralSighting],
    known_numerals: list[str],
) -> list[str]:
    """Which figures should ride beside these cited spans (RT-4's payoff rule).

    Two deterministic signals, union'd:
    - an explicit ``FIG. N`` reference in a cited span → that figure;
    - a known reference numeral recited in a cited span → every sheet OCR sighted
      it on → those sheets' assigned figures.

    Display-only (D21): this selects which drawing panels to SHOW next to the
    highlighted text — it asserts nothing and nothing here passes through
    `verify`. The numeral match is a token-boundary heuristic over short
    line-level spans; a spurious panel costs a glance, a missing one costs
    nothing (the standalone figures view still has everything).
    """
    import re as _re

    assigned = {a.fig for a in assignments}
    page_to_fig = {a.page: a.fig for a in assignments}
    num_to_pages: dict[str, set[int]] = {}
    for s in sightings:
        num_to_pages.setdefault(s.numeral, set()).add(s.page)

    out: set[str] = set()
    fig_ref = _re.compile(r"FIGS?\.?\s*(\d+[A-Z]?)", _re.IGNORECASE)
    for text in cited_span_texts:
        for m in fig_ref.finditer(text):
            if m.group(1).upper() in assigned:
                out.add(m.group(1).upper())
        for n in known_numerals:
            # standalone label n: not inside a larger/grouped/decimal number, and not
            # a prefix of a suffixed label ("12" must NOT match inside "12a") — hence
            # the trailing [\da-z] guard. A trailing `,` is punctuation ("10, which")
            # but `,\d` is grouping ("10,500").
            if _re.search(label_pattern(n), text):
                for page in num_to_pages.get(n, ()):
                    if page in page_to_fig:
                        out.add(page_to_fig[page])
    return sorted(out, key=lambda f: (len(f), f))


def numeral_text_figures(text: str, numeral: str, fig_refs, *,
                         window: int = FIGURE_CONTEXT_WINDOW) -> list[str]:
    """Every figure a numeral is discussed near across ALL its spec mentions — the
    nearest `FIG. N` reference at/before each standalone occurrence, within `window`
    chars. (`reference_numerals` gives only the FIRST mention; this sees them all, so
    "separator 10" discussed under both FIG. 1 and FIG. 4 surfaces both.)"""
    figs: set[str] = set()
    pat = re.compile(label_pattern(numeral))
    for m in pat.finditer(text):
        best = None
        for r in fig_refs:
            if r.char_start <= m.start() and m.start() - r.char_start <= window:
                if best is None or r.char_start > best.char_start:
                    best = r
        if best is not None:
            figs.add(best.number)
    return sorted(figs, key=lambda f: (len(f), f))


@dataclass(frozen=True)
class NumeralCoverage:
    figure_tied: list[str]         # the clean set: numerals the spec recites near a figure
    recited_not_drawn: list[str]    # figure-tied, but OCR found on NO sheet → OCR-miss flag
    drawn_not_recited: list[str]    # OCR-located, never recited in the spec → artefact/unlabeled
    figure_mismatches: list[dict]   # tied to FIG. N in text, not OCR-located on FIG. N's sheet
    seq_gaps: list[int]             # missing ints in figure_tied's range — WEAK (patents skip)


def numeral_coverage(
    numerals, text, fig_refs, assignments: list[SheetAssignment],
    sightings: list[NumeralSighting], *, min_confidence: float = 0.0,
) -> NumeralCoverage:
    """Reconcile the spec text vs. the drawings (OCR) and flag every numeral the two
    disagree on. Locate-only (D10): each flag is an OCR miss OR skipped numbering
    (patents routinely skip) OR a document limit — the check states the fact, never
    which.

    Design honesty (see the module's L0006-class lesson): the naive "are all
    CONSECUTIVE numbers present?" check is **not reliable** for patents — they skip
    reference numerals by design, and both quantities and OCR misreads corrupt the
    range — so `seq_gaps` is returned but flagged WEAK. The reliable checks are the
    reconciliation ones, which don't depend on enumerating a contiguous sequence:

    - `recited_not_drawn`: a **figure-tied** numeral (the spec recites it near a
      `FIG. N`, so it is a real reference numeral, not a quantity) that OCR located on
      no sheet at all — the strongest OCR-miss / missing-from-drawings signal.
    - `drawn_not_recited`: OCR read a number the spec never recites — an OCR artefact
      or a genuinely unlabelled element.
    - `figure_mismatches`: tied to FIG. N in text but not OCR-located on FIG. N's sheet
      (the separator-10 / FIG-4 case) — a per-figure OCR-miss.
    """
    text_nums = {n.number for n in numerals}
    sightings = [s for s in sightings if s.confidence >= min_confidence]
    ocr_nums = {s.numeral for s in sightings if s.numeral != "0"}   # "0" = OCR noise
    ocr_figs = numeral_figures(assignments, sightings)
    assigned_figs = {a.fig for a in assignments}

    text_figs_of = {n: [f for f in numeral_text_figures(text, n, fig_refs) if f in assigned_figs]
                    for n in text_nums}
    # TEXT-AUTHORITATIVE, figure-tied: numerals the spec recites in the context of a
    # figure. Excludes quantity noise ("220° F" — recited, not figure-tied) and OCR
    # misreads ("280" — on a sheet, never recited). The spec defines the numerals.
    figure_tied = sorted({n for n, fs in text_figs_of.items() if fs and n != "0"},
                         key=numeral_key)
    ints = sorted(int(n) for n in figure_tied if n.isdigit())   # suffixed labels excluded
    seq_gaps = ([i for i in range(ints[0], ints[-1] + 1) if i not in set(ints)] if ints else [])

    mismatches = []
    for n in figure_tied:
        missing = [f for f in text_figs_of[n] if f not in ocr_figs.get(n, [])]
        if missing:
            mismatches.append({
                "numeral": n, "text_figures": text_figs_of[n],
                "ocr_figures": ocr_figs.get(n, []), "not_located_on": missing,
                "message": (f"numeral {n} is discussed in the text in the context of "
                            f"FIG(S). {', '.join(missing)}, but OCR did not locate it there "
                            f"— an OCR miss or the number is not labeled on that sheet; review"),
            })
    return NumeralCoverage(
        figure_tied=figure_tied,
        recited_not_drawn=[n for n in figure_tied if n not in ocr_nums],
        drawn_not_recited=sorted(ocr_nums - text_nums, key=numeral_key),
        figure_mismatches=mismatches,
        seq_gaps=seq_gaps,
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
