"""annotate — a reviewer's drawn box, converted where it can be tested (RT-7c, D51).

A reviewer drags a rectangle over a sheet to assert a mark OCR never found. The browser
reports that in **pixels from the top-left of the displayed image**; the manifest stores
**normalized fractions with a bottom-left origin** (Vision's convention). Something has to
convert, and the choice of *where* matters more than it looks.

**The conversion lives here, in Python, not in the page.** A y-flip between these two
frames has already cost this project once — recovered boxes landed mirrored because a
Quartz tile rect is top-left while a Vision bbox is bottom-left (L0007) — and a transform
written in JavaScript is a transform no Layer-0 test can reach. One implementation, in the
language the gate runs in.

The page therefore sends what it actually knows — pixel corners and the displayed size —
and never its own idea of a normalized coordinate.

**What a drawn box is, and is not.** It is a human sighting: evidence with provenance,
recorded as a `confirm` adjudication naming who saw it and when. It does **not** trigger a
re-OCR of that region. OCR is an ingestion-time step whose output is frozen and hashed
(D28), and running an engine at review time would put a model call on the runtime path and
break the determinism the whole system rests on (I6). A box can *inform* a later ingestion
pass; it cannot quietly become one.
"""

from __future__ import annotations

from dataclasses import dataclass


class BoxError(ValueError):
    """A drawn box that cannot be a mark on this sheet."""


# Below this the "box" is a stray click, not a deliberate rectangle. Generous: a reference
# numeral on a 2300px sheet is a few dozen pixels, and refusing a real small mark is worse
# than accepting a slightly sloppy one.
MIN_SIDE_PX = 4


@dataclass(frozen=True)
class NormalizedBox:
    """A box in manifest coordinates: normalized, origin bottom-left."""

    x: float
    y: float
    w: float
    h: float

    def as_target(self, page: int, numeral: str) -> dict:
        return {"page": page, "numeral": numeral,
                "x": self.x, "y": self.y, "w": self.w, "h": self.h}


def box_from_pixels(x0: float, y0: float, x1: float, y1: float,
                    *, width: float, height: float) -> NormalizedBox:
    """Browser pixels (top-left origin) → manifest coordinates (bottom-left, normalized).

    Corners arrive in whatever order the drag produced, so they are ordered here rather
    than trusted. The y flip is the whole point:

        y_bottom = 1 - (y_top_normalized + h)

    i.e. the DISTANCE FROM THE BOTTOM of the box's lower edge — not `1 - y_top`, which
    would place the box one box-height off and is exactly the shape of the earlier bug.
    """
    if width <= 0 or height <= 0:
        raise BoxError(f"displayed size must be positive, got {width}x{height}")
    left, right = sorted((float(x0), float(x1)))
    top, bottom = sorted((float(y0), float(y1)))
    if (right - left) < MIN_SIDE_PX or (bottom - top) < MIN_SIDE_PX:
        raise BoxError(
            f"box is {right - left:.0f}x{bottom - top:.0f}px — that is a click, not a "
            f"rectangle. Drag across the mark you can see.")
    if left < 0 or top < 0 or right > width or bottom > height:
        raise BoxError("box extends outside the sheet")

    w = (right - left) / width
    h = (bottom - top) / height
    return NormalizedBox(
        x=round(left / width, 4),
        y=round(1.0 - (top / height) - h, 4),      # flip: distance from the BOTTOM
        w=round(w, 4),
        h=round(h, 4),
    )


def box_to_display(x: float, y: float, w: float, h: float) -> dict:
    """Manifest coordinates → fractions from the TOP-left, for drawing in a browser.

    The exact inverse of `box_from_pixels`, and it lives here for the same reason: the
    round trip is where a y-flip hides. A box drawn by a reviewer, stored, and drawn back
    must land on the same ink — so both directions are one tested pair rather than one
    tested function and one hopeful line of JavaScript.

        top = 1 - (y + h)

    because `y` is the distance from the bottom to the box's LOWER edge, and CSS wants
    the distance from the top to its UPPER edge.
    """
    return {"left": round(float(x), 6), "top": round(1.0 - (float(y) + float(h)), 6),
            "width": round(float(w), 6), "height": round(float(h), 6)}
