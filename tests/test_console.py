"""Standing tests for the console frame (RT-10, D48)."""

from __future__ import annotations

import re

import pytest

from cairn.console import ConsoleState, Pane, render

pytestmark = pytest.mark.layer0


def _state(**kw):
    base = dict(engagement="Test", doc_ids=["D1"], calibration="Floor 15.1, calibrated.",
                calibrated=True, contract="1.2", adjudications=2, generated_on="2026-07-28",
                panes=[Pane("evidence", "Evidence", "show the work", "evidence.html"),
                       Pane("locate", "Locate", "ask", None, "not built yet")])
    base.update(kw)
    return ConsoleState(**base)


def _text(page: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))


def test_an_uncalibrated_corpus_is_stated_in_the_persistent_header():
    """D33's rule, architecturally: a caveat that scrolls away is a caveat that did not
    work. The header sits above every pane, so an uncalibrated floor — which skews toward
    refusing answerable questions, and therefore reads as diligence — cannot be missed by
    a reviewer who never opens a settings tab."""
    page = render(_state(calibrated=False,
                         calibration="This corpus has NO calibration record — abstentions "
                                     "here are unreliable."))
    header = page[:page.index("<main")]
    assert "NO calibration record" in header
    assert "NOT calibrated" in header
    assert 'class="cal warn"' in header


def test_a_calibrated_corpus_does_not_cry_wolf():
    header = render(_state())[:render(_state()).index("<main")]
    assert 'class="cal ok"' in header
    assert "NOT calibrated" not in header


def test_absent_panes_say_what_is_missing_rather_than_disappearing():
    """A stage that silently vanishes is indistinguishable from one with no findings."""
    page = render(_state())
    assert "not built yet" in _text(page)
    assert "data-pane='locate'" in page, "the tab stays visible, dimmed"
    assert "class='dim'" in page


def test_every_pane_has_a_body_and_the_first_available_one_shows():
    page = render(_state())
    for key in ("evidence", "locate"):
        assert f"id='pane-{key}'" in page
    assert "id='pane-evidence'><iframe" in page, "the first available pane shows"
    assert "id='pane-locate' hidden" in page


def test_reviewer_judgments_are_visible_without_opening_a_pane():
    page = render(_state(adjudications=7))
    assert "7" in _text(page[:page.index("<main")])


def test_engagement_text_is_escaped():
    page = render(_state(engagement="<script>alert(1)</script>"))
    assert "<script>alert(1)</script>" not in page.replace("&lt;script&gt;", "")
    assert "&lt;script&gt;" in page
