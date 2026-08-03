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
