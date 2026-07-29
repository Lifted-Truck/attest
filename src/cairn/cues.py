"""Denial/correction cue scan (D24) — a deterministic MEASUREMENT, not a gate.

Finding of the provability swarm (docs/provability_research.md): the only slice of
"cited span refutes the cited figure" that is deterministically visible is the
**lexically marked, span-local** one — an evaluative denial/correction word sitting
near the bound figure ("…claimed $2,000,000, but in fact this is **incorrect**…").
This module detects exactly that slice, and nothing more.

Status under D24: this is a **measurement instrument + non-blocking advisory flag**.
It gates nothing and guarantees nothing at runtime. Promotion to a Layer-0
abstain-trigger is D25, which is *conditional on the base rate this instrument
measures* (scripts/census_denial_cues.py) — if cue-marked refutation is rare-to-
absent in real corpora, the gate is deprioritized on evidence.

Design constraints, from the research:
- **Closed cue set, evaluative denial/correction only.** Attribution verbs
  (reported, claimed, stated, alleged) are EXCLUDED — they are the corpora's own
  assertion vocabulary ("the Company reported net sales of…", "What is claimed
  is…") and would fire on nearly every good citation.
- **Span-local proximity** (char window within the cited span). The window is an
  admitted heuristic — small on purpose; a page-40 figure restated on page 240 is
  out of reach BY DESIGN (the ceiling, not a bug).
- The flag must never read as "refuted" (a discourse claim it cannot substantiate)
  — only "denial/correction cue near the citation; review".

Deterministic, stdlib-only, I6-clean.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# The closed evaluative-denial/correction set, verbatim from the D24 research row.
# Extensions require evidence (census hits/misses), not intuition — the set being
# CLOSED is what keeps the false-positive story auditable.
DENIAL_CUES = (
    "incorrect", "erroneous", "mistaken", "overstated",
    "restated", "superseded", "corrected", "revalued",
)
_CUE = re.compile(r"\b(" + "|".join(DENIAL_CUES) + r")\b", re.IGNORECASE)

# Span-local window (chars between cue and atom). Small on purpose (≈ one clause);
# widening it trades precision for reach and needs census evidence first.
CUE_WINDOW = 160


@dataclass(frozen=True)
class CueHit:
    cue: str            # the matched cue word (lowercased)
    cue_start: int      # offset of the cue within the scanned text
    cue_end: int
    atom_start: int     # offset of the nearest in-window atom
    distance: int       # chars between cue and that atom


def denial_cue_hits(
    text: str, atom_offsets: list[int], *, window: int = CUE_WINDOW,
) -> list[CueHit]:
    """Every closed-set cue in `text` within `window` chars of a bound-atom offset.

    Offsets are relative to `text` (the caller passes a cited span's text and the
    atom positions within it). Returns one hit per (cue occurrence) with its nearest
    in-window atom; a cue with no atom in range is NOT a hit — the scan is
    span-local by construction. Deterministic; order = text order.
    """
    hits: list[CueHit] = []
    for m in _CUE.finditer(text):
        best: tuple[int, int] | None = None          # (distance, atom_start)
        for a in atom_offsets:
            d = abs(m.start() - a)
            if d <= window and (best is None or d < best[0]):
                best = (d, a)
        if best is not None:
            hits.append(CueHit(m.group(1).lower(), m.start(), m.end(), best[1], best[0]))
    return hits
