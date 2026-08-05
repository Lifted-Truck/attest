"""Standing tests for the reviewer's drawn box (RT-7c, D51).

The conversion lives in Python precisely so these can exist: a y-flip between the
browser's top-left frame and the manifest's bottom-left frame has already cost this
project once (L0007), and a transform written in JavaScript is one no gate can reach.
"""

from __future__ import annotations

import pytest

from cairn.annotate import BoxError, box_from_pixels

pytestmark = pytest.mark.layer0


def test_the_y_flip_measures_from_the_bottom_edge():
    """The bug shape this exists to prevent: `1 - y_top` places the box one box-height
    off. The correct value is the distance from the bottom of the box's LOWER edge."""
    b = box_from_pixels(100, 200, 300, 400, width=1000, height=1000)
    assert (b.x, b.w, b.h) == (0.1, 0.2, 0.2)
    assert b.y == 0.6, "1 - 0.2(top) - 0.2(height) = 0.6, not 0.8"


def test_a_box_at_the_top_of_the_sheet_lands_near_y_1():
    """A mark drawn at the very top of the image is high in manifest coordinates."""
    b = box_from_pixels(0, 0, 50, 50, width=1000, height=1000)
    assert b.y == pytest.approx(0.95)


def test_a_box_at_the_bottom_lands_near_y_0():
    b = box_from_pixels(0, 950, 50, 1000, width=1000, height=1000)
    assert b.y == pytest.approx(0.0)


def test_corner_order_does_not_matter():
    """A drag can start from any corner, so the corners are ordered rather than trusted."""
    a = box_from_pixels(100, 200, 300, 400, width=1000, height=1000)
    for corners in ((300, 400, 100, 200), (300, 200, 100, 400), (100, 400, 300, 200)):
        assert box_from_pixels(*corners, width=1000, height=1000) == a


def test_non_square_sheets_normalize_per_axis():
    """Patent sheets are tall; normalizing both axes by one dimension would skew every
    box. 2320x3408 is the real US5447630A geometry."""
    b = box_from_pixels(232, 0, 464, 340.8, width=2320, height=3408)
    assert b.x == pytest.approx(0.1)
    assert b.w == pytest.approx(0.1)
    assert b.h == pytest.approx(0.1)


def test_a_click_is_refused_as_a_box():
    """A stray click must not become a recorded human sighting."""
    with pytest.raises(BoxError, match="that is a click"):
        box_from_pixels(100, 100, 102, 101, width=1000, height=1000)


def test_a_box_outside_the_sheet_is_refused():
    with pytest.raises(BoxError, match="outside the sheet"):
        box_from_pixels(900, 900, 1100, 1100, width=1000, height=1000)


def test_a_degenerate_display_size_is_refused():
    with pytest.raises(BoxError, match="positive"):
        box_from_pixels(0, 0, 10, 10, width=0, height=100)


def test_as_target_produces_the_manifest_shape():
    b = box_from_pixels(100, 200, 300, 400, width=1000, height=1000)
    t = b.as_target(page=3, numeral="A")
    assert t == {"page": 3, "numeral": "A", "x": 0.1, "y": 0.6, "w": 0.2, "h": 0.2}


def test_the_pane_never_computes_a_normalized_coordinate():
    """The split is the point: the page reports pixels and the displayed size, and the
    conversion happens where a Layer-0 test can reach it. A page that normalized on its
    own would reintroduce an untestable transform."""
    from cairn.annotate_pane import render
    page = render([{"page": 3, "file": "p3.png", "figures": "2"}],
                  reviewer="J. Smith", on="2026-07-28")
    assert "box_px" in page, "pixels are what the page sends"
    assert "width: r.width" in page and "height: r.height" in page
    # Scoped to the script, and to DIVISION by the display dimensions — normalizing is
    # the thing to forbid. An earlier version matched "1 - " inside `box.x1 - box.x0`,
    # which is the same string-sniffing crudeness this project keeps re-learning.
    script = page[page.index("<script>"):]
    for leak in ("/ r.width", "/r.width", "/ r.height", "/r.height"):
        assert leak not in script, f"page normalizes on its own: {leak!r}"


def test_the_pane_states_that_a_box_does_not_trigger_a_re_ocr():
    """A reviewer who believes they triggered a re-scan would read an empty result as
    evidence of absence. OCR is ingestion-time and frozen (D28); running an engine at
    review time would put a model call on the runtime path (I6)."""
    import re as _re

    from cairn.annotate_pane import render
    text = _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", render(
        [], reviewer="J. Smith", on="2026-07-28")))
    assert "does not re-run OCR" in text
    assert "ingestion-time" in text


def test_a_nameless_server_renders_the_pane_read_only():
    from cairn.annotate_pane import render
    page = render([{"page": 3, "file": "p3.png", "figures": ""}], reviewer=None, on=None)
    assert "Read-only" in page and "--reviewer" in page


def test_drawing_a_box_back_lands_on_the_same_ink():
    """The round trip is where a y-flip hides. A reviewer draws a box, it is stored in
    manifest coordinates, and the console draws it back — if either direction is wrong
    the mark moves, and a reviewer confirming it would be confirming the wrong thing."""
    from cairn.annotate import box_to_display
    W = H = 1000
    drawn = box_from_pixels(100, 200, 300, 400, width=W, height=H)
    back = box_to_display(drawn.x, drawn.y, drawn.w, drawn.h)
    assert back["left"] * W == pytest.approx(100)
    assert back["top"] * H == pytest.approx(200), "the box must return to where it was drawn"
    assert back["width"] * W == pytest.approx(200)
    assert back["height"] * H == pytest.approx(200)


def test_a_mark_at_the_top_of_the_sheet_draws_at_the_top():
    """The direction that would be invisible in a round trip if BOTH were flipped."""
    from cairn.annotate import box_to_display
    high = box_to_display(x=0.1, y=0.95, w=0.02, h=0.02)   # y near 1 = near the top
    assert high["top"] == pytest.approx(0.03), "high y must draw near the top edge"
    low = box_to_display(x=0.1, y=0.0, w=0.02, h=0.02)
    assert low["top"] == pytest.approx(0.98), "y=0 must draw near the bottom edge"


def _pane(marks):
    from cairn.annotate_pane import render
    return render([{"page": 3, "file": "p3.png", "figures": "2", "marks": marks}],
                  reviewer="J. Smith", on="2026-07-28")


def test_existing_marks_are_shown_with_their_labels():
    page = _pane([{"left": 0.1, "top": 0.2, "width": 0.03, "height": 0.02,
                   "numeral": "72", "x": 0.1, "y": 0.78, "human": False,
                   "engines": "vision,tesseract"}])
    assert '"numeral": "72"' in page.replace("'", '"') or '"numeral":"72"' in page
    assert "show the" in page and "marks already located" in page


def test_human_and_machine_marks_are_distinguishable():
    """A reviewer's own sighting must never be mistaken for an OCR read, or the record
    stops meaning anything (D28's honesty model, at the pixel)."""
    page = _pane([])
    assert 'data-human' in page
    assert '.mk[data-human="1"]' in page, "human marks get their own style"
    assert "recorded by" in page and "located by OCR" in page


def test_revising_and_removing_are_offered_but_never_edit():
    """Neither action edits the record: a revision appends a judgment naming what it
    supersedes, and both stay readable (D47)."""
    page = _pane([])
    assert "doCorrect" in page and "doRefute" in page
    assert "judge('correct'" in page and "judge('refute'" in page
    assert "Neither edits the record" in page
    assert "supersedes" in page


def test_the_pane_positions_marks_but_never_computes_their_position():
    """Same split as the drawing half: `box_to_display` converts in Python, the page
    only places what it is given."""
    page = _pane([])
    script = page[page.index("<script>"):]
    assert "m.left * 100" in script and "m.top * 100" in script
    for leak in ("1 - m.y", "1 - (m.y", "/ r.height", "/ r.width"):
        assert leak not in script, f"page computes its own position: {leak!r}"
