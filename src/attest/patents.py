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
