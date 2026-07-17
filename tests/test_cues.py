"""Standing tests for the D24 denial-cue scan (docs/provability_research.md, Rung 1).

The scanner itself is deterministic, so IT gets a real Layer-0 gate — on its own
behaviour, not on any answer outcome (it gates nothing; D24 is a measurement).
The fixture table asserts exact hits per the research's testing protocol:
a positive control, benign real-shaped spans that must NOT hit (they guard the
false-positive boundary D25 depends on), and a cue-less refutation that SHOULD be
missed — documented as the ceiling, so a future "improvement" that appears to catch
it is scrutinized as a possible over-trigger, not celebrated.
"""

from attest.cues import CUE_WINDOW, DENIAL_CUES, denial_cue_hits

# Julian's synthetic refutation case — the positive control. The figure atom sits at
# the offset of "2,000,000"; "incorrect" is ~40 chars downstream.
POSITIVE = ("When speaking of total assets and liabilities, the number $2,000,000 has "
            "been claimed, but in fact this is incorrect when accounting for the revaluation.")

# Benign spans shaped like the real corpora — none may hit.
BENIGN = [
    # contrast connective, no evaluative denial (10-K prose shape)
    ("Net sales rose to $391,035 million, but cost of sales also rose.", "391,035"),
    # attribution verb — EXCLUDED from the cue set by design
    ("The Company reported net sales of $391,035 million for fiscal 2024.", "391,035"),
    # patent assertion vocabulary
    ("What is claimed is: a treatment system rated at 400 W.", "400"),
]

# A cue-less refutation — the permanent ceiling. MUST be missed (asserted below).
CUELESS = ("The prior figure of $2,000,000 does not reflect the revaluation, which "
           "raises total assets and liabilities to $3,400,000.")


def _atom(text: str, literal: str) -> int:
    return text.index(literal)


def test_positive_control_hits_incorrect():
    hits = denial_cue_hits(POSITIVE, [_atom(POSITIVE, "2,000,000")])
    assert [h.cue for h in hits] == ["incorrect"]
    h = hits[0]
    assert POSITIVE[h.cue_start:h.cue_end].lower() == "incorrect"
    assert h.distance <= CUE_WINDOW


def test_benign_spans_do_not_hit():
    """The false-positive boundary — the load-bearing direction (precision >> recall).
    These become D25's CI gate if the scan is ever promoted to an abstain-trigger."""
    for text, literal in BENIGN:
        assert denial_cue_hits(text, [_atom(text, literal)]) == [], text


def test_cueless_refutation_is_missed_by_design():
    """The ceiling, pinned: refutation with no closed-set cue is invisible (the
    research's negative control). If this test ever 'passes better', something is
    over-triggering — investigate, don't celebrate."""
    assert denial_cue_hits(CUELESS, [_atom(CUELESS, "2,000,000")]) == []


def test_cue_outside_window_is_not_a_hit():
    """Span-local means span-local: the same cue beyond the window is out of scope
    BY DESIGN (a page-240 restatement of a page-40 figure is the ceiling, not a bug)."""
    far = "The figure $2,000,000 was cited. " + ("x" * (CUE_WINDOW + 30)) + " That was incorrect."
    assert denial_cue_hits(far, [_atom(far, "2,000,000")]) == []
    near = "The figure $2,000,000 was incorrect."
    assert len(denial_cue_hits(near, [_atom(near, "2,000,000")])) == 1


def test_cue_set_is_closed_and_excludes_attribution_verbs():
    """The set is the D24 list verbatim; attribution verbs are the corpora's own
    assertion vocabulary and must never enter it without a new decision row."""
    assert set(DENIAL_CUES) == {"incorrect", "erroneous", "mistaken", "overstated",
                                "restated", "superseded", "corrected", "revalued"}
    for verb in ("reported", "claimed", "stated", "alleged"):
        assert verb not in DENIAL_CUES


def test_multiple_atoms_pick_nearest():
    text = "Assets of $1,000 were restated; liabilities of $2,000 were unchanged."
    a1, a2 = _atom(text, "1,000"), _atom(text, "2,000")
    hits = denial_cue_hits(text, [a1, a2])
    assert len(hits) == 1 and hits[0].cue == "restated"
    assert hits[0].atom_start == a1                      # nearest, not first-listed
