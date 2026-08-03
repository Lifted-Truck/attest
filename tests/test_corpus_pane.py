"""Standing tests for the Corpus pane (RT-2, D52)."""

from __future__ import annotations

import re

import pytest

from cairn.corpus_pane import render

pytestmark = pytest.mark.layer0


def _p(**kw):
    base = dict(doc_ids=["D1"], hashes={"D1": "abc123"}, sizes={"D1": 1000},
                calibration="Floor 15.1, calibrated 2026-07-28.", calibrated=True,
                stale=False, fitted_untested=[("figures_map.MIN_LOCATABLE_NUMERAL",
                                               "A corpus whose single-digit numerals ARE "
                                               "reliably readable.")],
                sheets=8, adjudications=2, chain_ok=True)
    base.update(kw)
    return render(**base)


def _text(p: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))


def test_there_is_no_write_path_into_the_corpus():
    """RT-2 asked for ingest/remove buttons; this is a deliberate narrowing. Ingesting
    invalidates the fitted support floor, the offsets every logged citation resolves
    against, and the read-only-corpus posture the review server was argued for. It stays a
    considered CLI act, and the pane says why rather than quietly omitting it."""
    page = _p()
    assert "<form" not in page and "<input" not in page and "<button" not in page
    text = _text(page)
    assert "no “add document” button here, on purpose" in text.replace("&quot;", "“")
    assert "ingest_files.py" in text


def test_hashes_are_shown_for_independent_verification():
    assert "abc123" in _p()


def test_untested_constants_are_named_because_inert_is_not_validated():
    """D43's lesson surfaced to the reviewer: a constant no observation exercised has not
    been shown to transfer, and calling that a pass is how a fitted value becomes a law."""
    text = _text(_p())
    assert "MIN_LOCATABLE_NUMERAL" in text
    assert "Inert is not validated" in text


def test_an_uncalibrated_or_stale_floor_reads_as_a_warning():
    assert 'class="state warn"' in _p(calibrated=False,
                                      calibration="NO calibration record.")
    assert 'class="state warn"' in _p(stale=True, calibration="STALE CALIBRATION.")
    assert 'class="state ok"' in _p()


def test_a_broken_judgment_chain_is_not_reported_as_fine():
    assert "NOT VERIFIED" in _p(chain_ok=False)
    assert 'class="state warn"' in _p(chain_ok=False)
