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
             {"numeral": 10, "source_text": "10", "confidence": 1.0, "x": 0.4, "y": 0.3},
             {"numeral": 12, "source_text": "-12", "confidence": 0.3, "x": 0.5, "y": 0.3},
         ]},
        {"page": 3, "file": "drawings-page-3.png",
         "fig_labels": [{"fig": "A", "confidence": 0.5, "x": 0.5, "y": 0.03}],  # garbled "4"
         "sheet_id": {"sheet": 2, "of": 3},
         "numerals": [
             {"numeral": 89, "source_text": "89", "confidence": 1.0, "x": 0.6, "y": 0.4},
         ]},
        {"page": 4, "file": "drawings-page-4.png",
         "fig_labels": [{"fig": "5", "confidence": 1.0, "x": 0.5, "y": 0.03}],
         "sheet_id": {"sheet": 3, "of": 3},
         "numerals": [
             {"numeral": 77, "source_text": "77", "confidence": 1.0, "x": 0.2, "y": 0.5},
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
    assert [(s.numeral, s.page) for s in all_s] == [(10, 2), (12, 2), (89, 3), (77, 4)]
    high = numeral_sightings(MANIFEST, min_confidence=0.5)
    assert [(s.numeral, s.page) for s in high] == [(10, 2), (89, 3), (77, 4)]  # -12 dropped


def test_cross_check_three_classes():
    cc = cross_check_numerals([10, 89, 42], MANIFEST)
    assert sorted(cc.matched) == [10, 89]
    assert cc.text_only == [42]                          # recited, never located
    assert [(s.numeral, s.page) for s in cc.sheet_only] == [(12, 2), (77, 4)]


def test_element_numeral_issues_word_the_ocr_caveat():
    """PE-2's check surfaces facts with the indistinguishability caveat — never a
    §112 conclusion (D10)."""
    nums = [Numeral(10, "separator", 0, 2), Numeral(42, "ash outlet", 10, 12)]
    issues = element_numeral_issues(nums, MANIFEST, min_confidence=0.5)
    kinds = {(i["kind"], i["numeral"]) for i in issues}
    assert ("recited-not-located", 42) in kinds
    assert ("located-not-recited", 77) in kinds
    assert ("located-not-recited", 89) in kinds          # 89 not in the recited list here
    for i in issues:                                     # the honesty wording is load-bearing
        assert "indistinguishable" in i["message"] and "review" in i["message"]
        assert "112" not in i["message"] and "invalid" not in i["message"]


def _rel(span: str, known=(10, 12, 89, 77)):
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
    assert _rel("plain prose with no figure or numeral", known=[10]) == []
    assert _rel("FIG. 9 does not exist here", known=[10]) == []      # 9 not assigned
