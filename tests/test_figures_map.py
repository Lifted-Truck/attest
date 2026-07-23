"""Standing tests for the FIG→sheet / numeral→sheet mapping (RT-4/PE-2, D28).

The OCR itself runs once at ingestion (macOS Vision, local-only) and is NOT under
test here — these tests pin the DETERMINISTIC layer over a frozen manifest, with a
synthetic fixture, so they are hermetic and CI-runnable. The split is the point:
same manifest, same answers (I6); OCR variance is quarantined at ingestion.
"""

from attest.figures_map import (
    ELIMINATION,
    OCR,
    cross_check_numerals,
    element_numeral_issues,
    fig_to_sheets,
    numeral_sightings,
)
from attest.patents import Numeral

# A synthetic manifest shaped exactly like scripts/ocr_patent_figures.py output:
# three sheets — one clean label, one garbled label ("FIG.A", as Vision actually
# produced for FIG. 4 on US5447630A), one clean — plus numerals incl. a low-conf one.
MANIFEST = {
    "engine": "test-fixture",
    "pages": [
        {"page": 2, "file": "drawings-page-2.png",
         "fig_labels": [{"fig": "1", "confidence": 0.5, "x": 0.5, "y": 0.7}],
         "sheet_id": {"sheet": 1, "of": 3},
         "numerals": [
             {"numeral": "10", "source_text": "10", "confidence": 1.0,
              "x": 0.4, "y": 0.3, "w": 0.02, "h": 0.02},
             {"numeral": "12", "source_text": "-12", "confidence": 0.3,
              "x": 0.5, "y": 0.3, "w": 0.03, "h": 0.02},
         ]},
        {"page": 3, "file": "drawings-page-3.png",
         "fig_labels": [{"fig": "A", "confidence": 0.5, "x": 0.5, "y": 0.03}],  # garbled "4"
         "sheet_id": {"sheet": 2, "of": 3},
         "numerals": [
             {"numeral": "89", "source_text": "89", "confidence": 1.0,
              "x": 0.6, "y": 0.4, "w": 0.02, "h": 0.02},
         ]},
        {"page": 4, "file": "drawings-page-4.png",
         "fig_labels": [{"fig": "5", "confidence": 1.0, "x": 0.5, "y": 0.03}],
         "sheet_id": {"sheet": 3, "of": 3},
         "numerals": [
             {"numeral": "77", "source_text": "77", "confidence": 1.0,
              "x": 0.2, "y": 0.5, "w": 0.02, "h": 0.02},
         ]},
    ],
}
KNOWN = ["1", "4", "5"]


def test_fig_to_sheets_ocr_plus_single_gap_elimination():
    """Clean labels map by OCR; the garbled 'FIG.A' cannot invent figure A; with
    exactly one figure and one sheet left, they pair BY ELIMINATION — flagged."""
    got = {a.fig: a for a in fig_to_sheets(MANIFEST, KNOWN)}
    assert set(got) == {"1", "4", "5"}
    assert got["1"].page == 2 and got["1"].method == OCR and got["1"].confidence == 0.5
    assert got["5"].page == 4 and got["5"].method == OCR
    assert got["4"].page == 3 and got["4"].method == ELIMINATION
    assert got["4"].confidence is None                   # no fake confidence


def test_elimination_needs_a_unique_gap():
    """Two unassigned figures → no guessing: both stay unassigned (a surfaced gap)."""
    got = fig_to_sheets(MANIFEST, ["1", "4", "5", "6"])  # 6 has no sheet anywhere
    methods = {a.fig: a.method for a in got}
    assert "4" not in methods and "6" not in methods     # neither invented
    assert methods == {"1": OCR, "5": OCR}


def test_numeral_sightings_confidence_floor():
    all_s = numeral_sightings(MANIFEST)
    assert [(s.numeral, s.page) for s in all_s] == [("10", 2), ("12", 2), ("89", 3), ("77", 4)]
    high = numeral_sightings(MANIFEST, min_confidence=0.5)
    assert [(s.numeral, s.page) for s in high] == [("10", 2), ("89", 3), ("77", 4)]  # -12 dropped


def test_cross_check_three_classes():
    cc = cross_check_numerals(["10", "89", "42"], MANIFEST)
    assert sorted(cc.matched) == ["10", "89"]
    assert cc.text_only == ["42"]                          # recited, never located
    assert [(s.numeral, s.page) for s in cc.sheet_only] == [("12", 2), ("77", 4)]


def test_element_numeral_issues_word_the_ocr_caveat():
    """PE-2's check surfaces facts with the indistinguishability caveat — never a
    §112 conclusion (D10)."""
    nums = [Numeral("10", "separator", 0, 2), Numeral("42", "ash outlet", 10, 12)]
    issues = element_numeral_issues(nums, MANIFEST, min_confidence=0.5)
    kinds = {(i["kind"], i["numeral"]) for i in issues}
    assert ("recited-not-located", "42") in kinds
    assert ("located-not-recited", "77") in kinds
    assert ("located-not-recited", "89") in kinds          # 89 not in the recited list here
    for i in issues:                                     # the honesty wording is load-bearing
        assert "indistinguishable" in i["message"] and "review" in i["message"]
        assert "112" not in i["message"] and "invalid" not in i["message"]


def _rel(span: str, known=("10", "12", "89", "77")):
    from attest.figures_map import numeral_sightings, relevant_figures
    return relevant_figures([span], fig_to_sheets(MANIFEST, KNOWN),
                            numeral_sightings(MANIFEST), list(known))


def test_relevant_figures_by_numeral_and_ref():
    """RT-4 payoff: a cited span → the figures to show. Numeral 10 → its sheet's
    figure (1); an explicit FIG. 5 → figure 5; numeral 89 → the elimination-mapped
    figure 4; the two signals union and sort."""
    assert _rel("the separator 10, which splits flow") == ["1"]
    assert _rel("a necked portion 89 is provided") == ["4"]          # elimination-mapped
    assert _rel("as shown in FIG. 5 in cross-section") == ["5"]
    assert _rel("separator 10 and FIG. 5") == ["1", "5"]             # union


def test_relevant_figures_numeral_boundary():
    """A numeral must be a STANDALONE integer — not part of a larger/grouped/decimal
    number. Grouping comma ('10,500') excludes it; punctuation comma ('10, which')
    does not."""
    assert _rel("revenue of $10,500 thousand") == []                 # grouped
    assert _rel("a ratio of 10.5 to one") == []                      # decimal
    assert _rel("chamber 100 holds") == []                           # 100 ≠ 10
    assert _rel("the separator 10, however,") == ["1"]               # punctuation comma


def test_relevant_figures_unknown_signals_yield_nothing():
    assert _rel("plain prose with no figure or numeral", known=["10"]) == []
    assert _rel("FIG. 9 does not exist here", known=["10"]) == []      # 9 not assigned


def test_numeral_figures_all_appearances():
    """The 'all references' resolver: a numeral OCR-located on several sheets lists
    every figure it appears in (the user's shared-component case), sorted; an
    unassigned-sheet sighting contributes no figure."""
    from attest.figures_map import numeral_figures, numeral_sightings
    assigns = fig_to_sheets(MANIFEST, KNOWN)         # 1→p2, 4→p3(elim), 5→p4
    allf = numeral_figures(assigns, numeral_sightings(MANIFEST))
    assert allf["10"] == ["1"]                         # p2 → FIG 1
    assert allf["89"] == ["4"]                         # p3 → FIG 4 (elimination)
    assert allf["77"] == ["5"]                         # p4 → FIG 5


def test_numeral_sighting_carries_bbox():
    """Bounding boxes survive into the sighting for the confirmation overlay."""
    from attest.figures_map import numeral_sightings
    s = {(x.numeral, x.page): x for x in numeral_sightings(MANIFEST)}
    assert s[("10", 2)].bbox == (0.4, 0.3, 0.02, 0.02)
    assert s[("89", 3)].bbox == (0.6, 0.4, 0.02, 0.02)


def test_numeral_sighting_bbox_absent_is_none():
    """A legacy manifest without w/h yields bbox=None, not a crash."""
    from attest.figures_map import numeral_sightings
    legacy = {"pages": [{"page": 2, "file": "p.png", "fig_labels": [], "sheet_id": None,
                         "numerals": [{"numeral": "5", "source_text": "5",
                                       "confidence": 1.0, "x": 0.1, "y": 0.1}]}]}
    assert numeral_sightings(legacy)[0].bbox is None


def test_numeral_coverage_reconciliation():
    """The consistency check (Julian's ask): reconcile spec text vs OCR'd drawings.
    Reliable flags — recited-not-drawn, drawn-not-recited, per-figure mismatch —
    NOT the consecutive-integer check (unreliable for patents; returned as WEAK)."""
    from attest.figures_map import numeral_coverage
    from attest.patents import Numeral, figure_references
    # FIG1→p2 (OCR: 10,12), FIG4→p3 (OCR: 89), FIG5→p4 (OCR: 77) — from MANIFEST.
    text = ("As shown in FIG. 1, the separator 10 operates. "
            "In FIG. 5, the frame 12 and a gauge 34 are shown. "
            "In FIG. 4, the widget 89 is disassembled.")
    numerals = [Numeral(n, "x", 0, 1) for n in ("10", "12", "34", "89")]  # 77: nobody
    refs = figure_references(text)
    assigns = fig_to_sheets(MANIFEST, KNOWN)
    cov = numeral_coverage(numerals, text, refs, assigns, numeral_sightings(MANIFEST))

    assert cov.figure_tied == ["10", "12", "34", "89"]
    assert cov.recited_not_drawn == ["34"]        # tied to FIG 5 in text, OCR found it nowhere
    assert cov.drawn_not_recited == ["77"]        # OCR has 77 (p4), text never recites it
    mism = {m["numeral"]: m["not_located_on"] for m in cov.figure_mismatches}
    assert mism.get("12") == ["5"]                # text ties 12 to FIG 5, OCR has it on FIG 1
    assert "10" not in mism                        # 10 tied to FIG 1 AND OCR'd on FIG 1 → clean
    assert cov.seq_gaps                          # computed, but weak (not a shipped flag)


def test_numeral_text_figures_sees_all_mentions():
    """Unlike reference_numerals (first mention only), this finds every figure a
    numeral is discussed near — the basis of the separator-10 finding."""
    from attest.figures_map import numeral_text_figures
    from attest.patents import figure_references
    text = ("In FIG. 1 the separator 10 enters. Later, referring to FIG. 4, "
            "the disassembled separator 10 is shown.")
    refs = figure_references(text)
    assert numeral_text_figures(text, "10", refs) == ["1", "4"]     # both, not just the first


def test_numeral_sighting_method_round_trips():
    """D28 confirmation pass: a numeral record's `method` (first-pass | text-guided)
    survives into the sighting so the view can mark recovered numerals; a legacy
    record without the field defaults to first-pass."""
    from attest.figures_map import numeral_sightings
    man = {"pages": [{"page": 7, "file": "p.png", "fig_labels": [], "sheet_id": None,
                      "numerals": [
                          {"numeral": "10", "source_text": "10", "confidence": 0.3,
                           "x": 0.2, "y": 0.56, "w": 0.08, "h": 0.02, "method": "text-guided"},
                          {"numeral": "80", "source_text": "80", "confidence": 1.0,
                           "x": 0.7, "y": 0.6, "w": 0.02, "h": 0.02},  # no method → first-pass
                      ]}]}
    by = {s.numeral: s for s in numeral_sightings(man)}
    assert by["10"].method == "text-guided"
    assert by["80"].method == "first-pass"


def test_plain_label_does_not_match_inside_a_suffixed_one():
    """Boundary: searching for "12" must NOT fire on "12a" (a different part)."""
    assert _rel("the bracket 12a is welded", known=["12"]) == []
    assert _rel("the housing 12 is welded", known=["12"]) == ["1"]


MULTI = {
    "pages": [{"page": 2, "file": "p.png",
               "fig_labels": [{"fig": "1", "confidence": 1.0, "x": 0.5, "y": 0.7}],
               "sheet_id": None,
               "numerals": [        # the SAME label twice on one sheet (FIG 3A does this)
                   {"numeral": "12a", "source_text": "12a", "confidence": 1.0,
                    "x": 0.20, "y": 0.70, "w": 0.03, "h": 0.02, "method": "text-guided"},
                   {"numeral": "12a", "source_text": "12a", "confidence": 0.9,
                    "x": 0.60, "y": 0.30, "w": 0.03, "h": 0.02, "method": "text-guided"},
               ]}],
}


def test_same_label_twice_on_a_sheet_keeps_both_instances():
    """A label legitimately repeats on one drawing — both instances survive so the
    reviewer gets a confirmation box on each (Julian: 12a appears twice on FIG 3A)."""
    from attest.figures_map import numeral_figures, numeral_sightings
    sights = [s for s in numeral_sightings(MULTI) if s.numeral == "12a"]
    assert len(sights) == 2
    assert {s.bbox[0] for s in sights} == {0.20, 0.60}      # two distinct positions
    # but it is still ONE figure association, not a duplicate
    assigns = fig_to_sheets(MULTI, ["1"])
    assert numeral_figures(assigns, sights)["12a"] == ["1"]
