"""Patent document model (PE-1) — structure over the shared canonical text.

The patent counterpart to `edgar.py`: a **post-ingest parsing layer** that turns a
patent's canonical text into addressable objects whose provenance is exact char
offsets into that text (so `SpanStore.get_span` resolves each, hash-verified, I3).
It builds on the shared `Document`/`SpanStore` — no separate store.

This first increment models **claims** — discrete, numbered, independent/dependent,
with a parsed dependency — the structural heart of a patent. Spec-paragraph
numbering (`[0042]`), reference numerals, bibliographic front-matter, and the
priority chain are subsequent PE-1 increments.

**Cardinal rule (D10): locate & evidence, never adjudicate.** This module *locates*
claim structure; it never opines on validity, infringement, or claim scope.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .retrieval import BM25Backend
from .spans import Span

# Section marker preceding the claims, e.g. "What is claimed is:" / "We claim:".
_CLAIMS_MARKER = re.compile(
    r"(?im)^\s*(?:what is claimed is|we claim|i claim|the invention claimed is|claims)\s*:?\s*$"
)
# A claim starts at a number + period at the start of a line: "1. A device ...".
_CLAIM_START = re.compile(r"(?m)^[ \t]*(\d+)\.\s")
# A dependency reference inside a claim body: "... of claim 1, wherein ...".
_DEP_REF = re.compile(r"\bclaims?\s+(\d+)", re.IGNORECASE)

INDEPENDENT = "independent"
DEPENDENT = "dependent"

# Claim transition: the body (the limitations) begins after it.
_TRANSITION = re.compile(
    r"\b(comprising|comprises|consisting essentially of|consisting of|including|"
    r"wherein|characterized in that|having|the steps of)\b",
    re.IGNORECASE,
)
_LEAD_CONJ = re.compile(r"^(and|or)\b\s*", re.IGNORECASE)


@dataclass(frozen=True)
class Claim:
    number: int
    text: str
    char_start: int
    char_end: int
    kind: str                 # INDEPENDENT | DEPENDENT
    depends_on: int | None    # the claim this one references, or None


@dataclass(frozen=True)
class Limitation:
    claim_number: int
    index: int                # 0-based position within the claim
    text: str
    char_start: int
    char_end: int


# Native paragraph numbering (post-~2001 patents): [0001], [0042].
_PARA_NUM = re.compile(r"\[(\d{3,4})\]")
# Where the specification body starts (older patents lack [NNNN]).
_SPEC_START = re.compile(
    r"(?im)^\s*(detailed description|description|field of the invention|background)\b.*$"
)


@dataclass(frozen=True)
class Paragraph:
    label: str                # "[0042]" (native) or "¶N" (sequential)
    index: int
    text: str
    char_start: int
    char_end: int


def parse_paragraphs(text: str) -> list[Paragraph]:
    """Address the specification as paragraph spans (PE-1).

    Native `[NNNN]` numbering when present (modern patents); otherwise each
    description line is a paragraph (older patents — the spec is one paragraph per
    line). Offsets are absolute (`text[p.char_start:p.char_end] == p.text`), so each
    paragraph resolves through `SpanStore` — the spec side of PE-3's claim→spec
    support mapping. Excludes the claims section.
    """
    cm = _CLAIMS_MARKER.search(text)
    end = cm.start() if cm else len(text)

    marks = list(_PARA_NUM.finditer(text[:end]))
    out: list[Paragraph] = []
    if marks:
        for i, m in enumerate(marks):
            s = m.start()
            e = marks[i + 1].start() if i + 1 < len(marks) else end
            body = text[s:e].rstrip()
            out.append(Paragraph(f"[{m.group(1)}]", len(out), body, s, s + len(body)))
        return out

    hm = _SPEC_START.search(text[:end])
    region_start = hm.end() if hm else 0
    for m in re.finditer(r".+", text[region_start:end]):       # each non-empty line
        s, e = region_start + m.start(), region_start + m.end()
        out.append(Paragraph(f"¶{len(out) + 1}", len(out), text[s:e], s, e))
    return out


# --- claim-limitation → specification support mapping (PE-3) ----------------------
# For each claim limitation, surface the spec paragraphs whose text most supports it
# (ranked, plural, each an addressable span). Deterministic — BM25 over the paragraph
# set (reuses the engine; I6). **Locate & evidence, never adjudicate (D10/§2):** an
# empty list is "no clear textual support *located*", NOT "support is legally
# insufficient / the claim lacks written description" — that is a professional's call.

# --- structural checks (PE-2) ----------------------------------------------------
# Deterministic, no-model checks that *surface* structural facts for review. Only
# the high-precision ones ship: claim-dependency integrity is objective (a missing
# or forward reference is a fact). The §112 heuristics (antecedent basis,
# element-numeral, term consistency) need precise NLP — a naive numeral check flags
# 34/67 numerals on US5447630A (mostly false positives: "at 92", "of 18", plurals),
# which would bury real issues; deferred until they can be done at high precision.
# Even here: state the structural fact, never conclude invalidity (D10).


@dataclass(frozen=True)
class StructuralIssue:
    kind: str                 # "dependency"
    claim_number: int
    message: str
    char_start: int
    char_end: int


def check_dependencies(claims: list[Claim]) -> list[StructuralIssue]:
    """Claim-dependency integrity: every dependent claim must reference an existing,
    earlier claim (no missing, self-, or forward references). Objective — surfaces
    the fact, not a validity conclusion."""
    numbers = {c.number for c in claims}
    issues: list[StructuralIssue] = []
    for c in claims:
        d = c.depends_on
        if d is None:
            continue
        if d not in numbers:
            msg = f"claim {c.number} depends on claim {d}, which does not exist"
        elif d >= c.number:
            rel = "itself" if d == c.number else f"a later claim ({d})"
            msg = f"claim {c.number} references {rel}, not an earlier claim"
        else:
            continue
        issues.append(StructuralIssue("dependency", c.number, msg, c.char_start, c.char_end))
    return issues


SUPPORT_EDGE = "CLAIM_LIMITATION→SPEC_SUPPORT"


@dataclass(frozen=True)
class SupportEdge:
    edge_type: str            # SUPPORT_EDGE (typed provenance, §4)
    claim_number: int
    limitation_index: int
    limitation_text: str
    paragraph_label: str      # the supporting spec paragraph
    score: float
    doc_id: str
    char_start: int           # the paragraph span (resolvable via SpanStore)
    char_end: int


def _spec_index(paragraphs: list[Paragraph], doc_id: str) -> BM25Backend:
    return BM25Backend([
        Span(f"{doc_id}@{p.char_start}-{p.char_end}", doc_id, p.char_start, p.char_end, p.text)
        for p in paragraphs
    ])


def map_claim_support(
    claim: Claim, paragraphs: list[Paragraph], doc_id: str, *, k: int = 5, floor: float = 0.0,
) -> list[tuple[Limitation, list[SupportEdge]]]:
    """Map each of a claim's limitations to its supporting spec paragraphs (ranked).

    Returns one `(limitation, edges)` pair per limitation; an **empty** `edges` list
    is a *surfaced gap* (no clear textual support located) — never a legal conclusion
    (D10). `floor` filters weak matches; it is a per-corpus knob (calibratable like
    the support threshold, D20), not a sufficiency judgment.
    """
    index = _spec_index(paragraphs, doc_id)
    by_start = {p.char_start: p for p in paragraphs}
    out: list[tuple[Limitation, list[SupportEdge]]] = []
    for lim in decompose_claim(claim):
        edges = []
        for h in index.search(lim.text, k):
            if h.score <= floor:
                continue
            p = by_start[h.span.char_start]
            edges.append(SupportEdge(
                SUPPORT_EDGE, claim.number, lim.index, lim.text, p.label,
                round(h.score, 2), doc_id, p.char_start, p.char_end))
        out.append((lim, edges))
    return out


def decompose_claim(claim: Claim) -> list[Limitation]:
    """Split a claim into its limitation clauses, each an addressable span.

    First cut: the body after the transition word (`comprising`/`wherein`/…) split
    on semicolons — the canonical claim-element delimiter. Each limitation's offsets
    are absolute, so `text[c.char_start:c.char_end] == c.text` and `SpanStore`
    resolves it (I3). Nested sub-elements ("…including: a; b; c") come out flat, and
    a `wherein` dependent with no semicolons yields one limitation — both refinable
    later. Locate-only (D10): structure, never a scope/validity opinion.
    """
    text, base = claim.text, claim.char_start
    m = _TRANSITION.search(text)
    if m:
        i = m.end()
        while i < len(text) and text[i] in " :\n\t":   # skip the transition's colon
            i += 1
        body_start = i
    else:                                              # no transition → skip "N." only
        nm = re.match(r"\s*\d+\.\s*", text)
        body_start = nm.end() if nm else 0

    out: list[Limitation] = []
    for seg in re.finditer(r"[^;]+", text[body_start:]):
        s, e = body_start + seg.start(), body_start + seg.end()
        while s < e and text[s] in " \n\t":            # trim leading whitespace
            s += 1
        lead = _LEAD_CONJ.match(text[s:e])             # drop a leading "and"/"or"
        if lead:
            s += lead.end()
        while e > s and text[e - 1] in " \n\t.,;":      # trim trailing ws/punctuation
            e -= 1
        if e > s:
            out.append(Limitation(claim.number, len(out), text[s:e], base + s, base + e))
    return out


def parse_claims(text: str) -> list[Claim]:
    """Parse the claims section of a patent's canonical text into addressable Claims.

    Offsets are absolute into ``text`` — ``text[c.char_start:c.char_end] == c.text``
    — so a claim is citable like any span. Returns ``[]`` if no claims section is
    found. Dependency is the first ``claim N`` the body references (a
    multiple-dependent claim records its first referent; full multi-dependency is a
    later refinement).
    """
    marker = _CLAIMS_MARKER.search(text)
    region_start = marker.end() if marker else 0
    starts = [
        (int(m.group(1)), region_start + m.start(1))
        for m in _CLAIM_START.finditer(text[region_start:])
    ]
    claims: list[Claim] = []
    for i, (number, start) in enumerate(starts):
        end_raw = starts[i + 1][1] if i + 1 < len(starts) else len(text)
        body = text[start:end_raw].rstrip()
        ref = _DEP_REF.search(body)
        depends_on = int(ref.group(1)) if ref else None
        kind = DEPENDENT if depends_on is not None else INDEPENDENT
        claims.append(Claim(number, body, start, start + len(body), kind, depends_on))
    return claims


# --- bibliographic front matter + priority/regime (PE-4) --------------------------
# Parses the INID-coded front page into addressable fields, derives the effective
# filing date (earliest of filing + claimed priority dates — a DATE fact), and
# flags the pre-AIA/AIA regime by comparison to 2013-03-16. The comparison is
# arithmetic over cited dates (D19's spirit); whether the regime *legally applies*
# to a given claim (e.g. mixed-priority applications) is a professional's call (D10).

_DATE_TXT = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? \d{4})"
)
_MONTHS = {m: i + 1 for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split())}
AIA_DATE = (2013, 3, 16)


def _parse_date(text: str) -> tuple[int, int, int] | None:
    m = re.match(r"([A-Za-z]+)\.? (\d{1,2}),? (\d{4})", text.strip())
    if not m:
        return None
    mon = _MONTHS.get(m.group(1).lower()[:3])
    return (int(m.group(3)), mon, int(m.group(2))) if mon else None


@dataclass(frozen=True)
class FrontMatter:
    patent_number: str | None
    date_of_patent: str | None    # verbatim, e.g. "Sep. 5, 1995"
    inventors: list[str]
    application_number: str | None
    filed: str | None             # verbatim, e.g. "Apr. 28, 1993"
    priority_claims: list[str]    # verbatim (60)/(63)-style lines, if any


def parse_front_matter(text: str) -> FrontMatter:
    """Parse the INID-coded front page (first ~40 lines) into addressable fields.
    Locate-only: fields are verbatim strings from the document."""
    head = "\n".join(text.split("\n")[:40])

    def grab(pattern: str) -> str | None:
        m = re.search(pattern, head)
        return m.group(1).strip() if m else None

    number = grab(r"United States Patent\s+(US [\d,]+\s?[A-Z]?\d?)")
    dop = grab(r"Date of Patent:\s*" + _DATE_TXT.pattern)
    inv = grab(r"\(7[25]\)\s*Inventors?:\s*(.+)")
    inventors = [i.strip() for i in re.split(r";|(?<!\bInc)\.,", inv)] if inv else []
    appno = grab(r"\(21\)\s*Appl\.? No\.?:\s*([\w/,]+)")
    filed = grab(r"\(22\)\s*Filed:\s*" + _DATE_TXT.pattern)
    priority = [ln.strip() for ln in head.split("\n")
                if re.match(r"\s*\((?:60|63)\)", ln)]
    return FrontMatter(number, dop, inventors, appno, filed, priority)


def effective_filing(fm: FrontMatter) -> tuple[str, tuple[int, int, int]] | None:
    """Earliest of the filing date and any claimed-priority dates — returned with the
    verbatim source text so the derivation cites its evidence."""
    cands: list[tuple[tuple[int, int, int], str]] = []
    if fm.filed:
        d = _parse_date(fm.filed)
        if d:
            cands.append((d, f"(22) Filed: {fm.filed}"))
    for line in fm.priority_claims:
        m = _DATE_TXT.search(line)
        d = _parse_date(m.group(1)) if m else None
        if d:
            cands.append((d, line))
    if not cands:
        return None
    d, src = min(cands)
    return src, d


def regime_flag(fm: FrontMatter) -> dict | None:
    """Pre-AIA/AIA flag as date arithmetic over cited front-matter dates (PE-4).
    Surfaces the comparison + its evidence; never asserts which regime governs a
    specific claim's examination — that is a professional's determination (D10)."""
    eff = effective_filing(fm)
    if eff is None:
        return None
    src, d = eff
    return {
        "effective_filing_date": f"{d[0]:04d}-{d[1]:02d}-{d[2]:02d}",
        "basis": src,
        "comparison": f"filed {'before' if d < AIA_DATE else 'on/after'} 2013-03-16",
        "flag": "pre-AIA" if d < AIA_DATE else "AIA",
        "note": "date arithmetic over the cited filing/priority text; regime "
                "applicability to specific claims is a professional determination (D10)",
    }


# --- figures + reference numerals (PE-1 remainder; the model RT-4 renders) ---------
# Patents are read through their drawings: claims and the spec turn on reference
# numerals that point into the figures. This models three addressable, text-only
# things — (1) each figure's caption from the "brief description of the drawings",
# (2) every in-text FIG. N reference, (3) the numeral→element first-mention map — so
# the GUI can surface the drawing when a cited numeral / FIG. N is in view.
#
# **Truth-contract boundary (D21/RT-4):** a figure is *displayed evidence*, not a
# text span. Grounding still binds a claim to the TEXT that recites a numeral; the
# drawing is shown alongside via a typed SPEC→FIGURE edge, never asserted as a
# textual citation. Locate-only (D10): this surfaces structure, never construes it.

# A figure caption in the drawings description: "FIG. 1 is an overall schematic …".
# The verb must follow the label directly, which distinguishes a *caption* from a
# detailed-description reference ("FIG. 4, a perspective view …" — comma, no verb).
_FIG_CAPTION = re.compile(
    r"FIGS?\.?\s*(\d+[A-Z]?)\s+(?:is|are|shows?|depicts?|illustrates?|"
    r"comprises?|represents?)\b",
    re.IGNORECASE,
)
# Any FIG reference (offset-bearing), incl. "FIGS. 4-5" and "FIG.5".
_FIG_REF = re.compile(r"FIGS?\.?\s*(\d+[A-Z]?)(?:\s*[-–]\s*(\d+[A-Z]?))?", re.IGNORECASE)
# Numeral first mention: "<element phrase> N" — 1–3 words naming the element, then the
# number. Leading article stripped; a preposition/adverb right before the number is not
# an element (drops "shown at 18", "generally by reference numeral 26").
#
# **No magnitude floor.** An earlier cut required numerals ≥10 on the folk rule that
# "patent numerals start at 10". That is NOT a safe general rule and it was wrong here:
# US5447630A labels its FIG. 1 greywater sources "bathtub or shower 1, toilet 2, …
# dishwasher 4 and clothes washer 5" — the floor silently deleted five real numerals.
# The actual discriminators are structural, not numeric:
#   · REGION — reference numerals live in the specification; "of claim 6" noise is an
#     artefact of scanning the claims, so we simply don't scan them.
#   · DECIMALS — "measured as 0.24 mg/l" must not yield numeral 0.
#   · UNITS — "400 W", "60 degrees" are quantities, not pointers.
_NUMERAL = re.compile(r"\b((?:the |a |an |said )?(?:[a-z]+ ){0,2}[a-z]+)\s+(\d{1,3})\b(?!\.\d)")
_UNIT_AFTER = re.compile(
    r"^\s*(?:W|watts?|mm|cm|m|in|inch(?:es)?|ft|kg|lbs?|°|degrees?|%|percent|hours?|"
    r"minutes?|seconds?|volts?|V|Hz|psi|gal|gallons?|l(?:iters?)?|N\.T\.U\.|mg)\b",
    re.IGNORECASE,
)
_NOT_ELEMENT = frozenset(
    "at by to of from in on and or is are than about over under approximately as "
    "reference numeral generally designated designate shown between within claim claims".split()
)
SPEC_FIGURE_EDGE = "SPEC→FIGURE"     # typed provenance (§4): displayed, not cited
_CAPTION_GAP = 400                   # max chars between consecutive drawings captions


@dataclass(frozen=True)
class Figure:
    label: str                # "FIG. 1"
    number: str               # "1", "3A"
    description: str          # the caption text (from the drawings description)
    char_start: int
    char_end: int


@dataclass(frozen=True)
class FigureRef:
    number: str               # the figure this reference points at
    char_start: int           # offset of the "FIG. N" token (SPEC→FIGURE anchor)
    char_end: int


@dataclass(frozen=True)
class Numeral:
    number: int
    element: str              # the noun phrase the numeral labels ("separator")
    char_start: int          # first-mention offset (element+number), resolvable
    char_end: int


def parse_figures(text: str) -> list[Figure]:
    """Each figure's caption, from the drawings description, as an addressable span.

    Keys off the `FIG. N <verb>` caption pattern rather than a section header —
    older patents (e.g. US5447630A) introduce the captions inline ("…the drawings
    in which: FIG. 1 is …") with no "Brief Description of the Drawings" heading. The
    captions are a single **contiguous run** (semicolon-joined); we take the first
    such run and stop at the first large gap, so a later "…the dimensions in FIG. 1
    are provided…" in the detailed description is not mistaken for a caption. Each
    caption runs from its label to the next (or the terminating period), so
    `text[f.char_start:f.char_end] == f.description` resolves through `SpanStore`.
    Locate-only — the caption is the patent's own words (D10). Range/sub-figure
    captions ("FIGS. 3A-3C are …") are not yet split per sub-figure — refinable.
    """
    caps = list(_FIG_CAPTION.finditer(text))
    block: list[re.Match] = []
    for m in caps:                                     # first contiguous caption run
        if block and m.start() - block[-1].end() > _CAPTION_GAP:
            break
        block.append(m)
    out: list[Figure] = []
    for i, m in enumerate(block):
        if i + 1 < len(block):
            end = block[i + 1].start()
        else:                                          # last caption: end at a period
            dot = text.find(".", m.end())
            end = dot + 1 if dot != -1 else len(text)
        desc = text[m.start():end].rstrip(" ;\n\t")
        out.append(Figure(f"FIG. {m.group(1)}", m.group(1), desc, m.start(), m.start() + len(desc)))
    return out


def figure_references(text: str) -> list[FigureRef]:
    """Every in-text FIG. N reference with its offset (a range like FIGS. 4-5 yields
    one ref per endpoint) — the SPEC→FIGURE anchors the GUI lights when a cited span
    is in view."""
    out: list[FigureRef] = []
    for m in _FIG_REF.finditer(text):
        out.append(FigureRef(m.group(1), m.start(), m.end()))
        if m.group(2):                                 # "FIGS. 4-5" → also the 5
            out.append(FigureRef(m.group(2), m.start(), m.end()))
    return out


def reference_numerals(text: str) -> list[Numeral]:
    """The numeral→element first-mention map (one entry per numeral, first mention).

    Scans the **specification only** (the claims are excluded — that is what removes
    "of claim 6"-style noise, structurally, rather than by guessing at magnitudes).
    Rejects decimals ("measured as 0.24 mg/l" is not numeral 0) and quantities carrying
    a unit ("400 W"). A leading article is trimmed and prepositional lead-ins rejected.

    **Deliberately permissive on value:** there is no minimum numeral — single-digit
    reference numerals are real (US5447630A: "toilet 2", "dishwasher 4"). Over-filtering
    silently deletes evidence, which is the worse failure for this system; a loose
    element phrase is a visible hint a reviewer can discount, a dropped numeral is
    invisible. Locate-only (D10): never claims which figure depicts a numeral — that
    needs the image. Element-phrase precision remains refinable.
    """
    cm = _CLAIMS_MARKER.search(text)
    region = text[:cm.start()] if cm else text          # specification only
    seen: dict[int, Numeral] = {}
    for m in _NUMERAL.finditer(region):
        phrase = re.sub(r"^(the|a|an|said)\s+", "", m.group(1).strip())
        if not phrase or phrase.split()[-1] in _NOT_ELEMENT:
            continue
        if _UNIT_AFTER.match(region[m.end():m.end() + 14]):    # a quantity, not a pointer
            continue
        num = int(m.group(2))
        if num in seen:                                # first mention only
            continue
        s = m.start() + (m.group(0).find(phrase))
        seen[num] = Numeral(num, phrase, s, m.end())
    return [seen[n] for n in sorted(seen)]
