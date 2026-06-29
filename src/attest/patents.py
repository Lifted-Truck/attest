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


@dataclass(frozen=True)
class Claim:
    number: int
    text: str
    char_start: int
    char_end: int
    kind: str                 # INDEPENDENT | DEPENDENT
    depends_on: int | None    # the claim this one references, or None


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
