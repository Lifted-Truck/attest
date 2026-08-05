"""Standing tests for the record of inquiry (RT-5, D46).

The report is a client-facing legal-adjacent artifact, so its *wording* is behaviour and
is tested as such. The rules it must not break come from the landscape survey's read of
what makes such a record an asset rather than a liability.
"""

from __future__ import annotations

import re

import pytest

from cairn.calibration import CalibrationRecord, corpus_hash, write
from cairn.ingest.document import make_document
from cairn.ingest.store import DocumentStore
from cairn.review_report import (
    LIMITS,
    CorpusIdentity,
    ReportData,
    corpus_identity,
    rejected_candidates,
    render,
)

pytestmark = pytest.mark.layer0


def _store(tmp_path):
    s = DocumentStore(tmp_path / "store")
    s.write(make_document("D1", "Total assets $ 364,980 as of September 28, 2024."))
    return s


def _data(corpus, interactions=(), entries=()):
    return ReportData("Test engagement", corpus, list(interactions),
                      list(entries), "2026-07-28")


def _text(html_str: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_str))


def test_the_limits_arrive_before_the_findings(tmp_path):
    """D33's discipline applied to the deliverable: a caveat a reader meets at the end is
    a caveat that did not work. The limits block must precede every findings section."""
    page = render(_data(corpus_identity(tmp_path / "store", _store(tmp_path))))
    limits_at = page.index('class="limits"')
    for heading in ("What was searched", "Outcomes", "Surfaced and set aside"):
        assert limits_at < page.index(heading), f"limits must precede '{heading}'"


def test_every_declared_limit_is_rendered(tmp_path):
    page = _text(render(_data(corpus_identity(tmp_path / "store", _store(tmp_path)))))
    for title, _ in LIMITS:
        assert title in page, f"declared limit missing from the report: {title}"


def test_it_never_claims_to_discharge_the_inquiry(tmp_path):
    """The load-bearing wording rule: this record *evidences*, *documents* and *supports*
    an inquiry — it never *satisfies*, *ensures* or *discharges* one. A record implying
    search breadth it does not have is a liability artifact. Checked as a CLAIM, not as a
    word count: 'discharge' is fine in "does not discharge it" and fatal without the
    negation."""
    page = _text(render(_data(corpus_identity(tmp_path / "store", _store(tmp_path)))))
    for verb in ("discharge", "satisf", "ensure"):
        for m in re.finditer(rf"\w*{verb}\w*", page, re.IGNORECASE):
            window = page[max(0, m.start() - 60):m.start()].lower()
            ctx = page[max(0, m.start() - 60):m.end() + 20]
            assert "not" in window or "non-delegable" in window, (
                f"unqualified claim to {m.group(0)!r} the inquiry: …{ctx}…")


def test_the_search_breadth_caveat_is_present(tmp_path):
    """A reader must not be able to infer exhaustiveness from a ranked BM25 slice."""
    page = _text(render(_data(corpus_identity(tmp_path / "store", _store(tmp_path)))))
    assert "ranked slice, not an exhaustive search" in page
    assert "does not establish" in page.lower() or "Nothing here establishes" in page


def test_corpus_hashes_are_published_for_independent_verification(tmp_path):
    store = _store(tmp_path)
    page = render(_data(corpus_identity(tmp_path / "store", store)))
    assert store.load("D1").content_hash in page, "the reader must be able to re-hash"


def test_an_uncalibrated_corpus_says_so_in_the_report(tmp_path):
    """RT-9's warning must reach the CLIENT-facing surface, not only the audit log —
    abstentions under a foreign floor are the ones a reviewer would otherwise trust."""
    ident = corpus_identity(tmp_path / "store", _store(tmp_path))
    assert not ident.calibrated
    page = _text(render(_data(ident)))
    # The claim, not the phrasing: the wording is now produced in one place
    # (calibration.describe) so every surface says the same thing (D53).
    assert "NO calibration record" in page
    assert "refusing questions the documents can in fact answer" in page


def test_a_calibrated_corpus_reports_its_provenance(tmp_path):
    store = _store(tmp_path)
    ids = store.list_docs()
    write(tmp_path / "store", CalibrationRecord(
        threshold=15.1, corpus_id="test", doc_ids=ids,
        corpus_hash=corpus_hash(ids, [store.load(d).content_hash for d in ids]),
        calibrated_on="2026-07-28", method="golden-gap", n_present=13, n_absent=3))
    ident = corpus_identity(tmp_path / "store", store)
    assert ident.calibrated
    assert "golden-gap" in ident.calibration and "15.1" in ident.calibration


def test_set_aside_candidates_are_reported_not_hidden():
    """A record showing only what was USED invites the reading that nothing else was
    seen. What was surfaced and set aside is what makes the inquiry's shape auditable —
    and it is the half a reviewer needs in order to disagree with it."""
    entries = [{"kind": "check_support", "query": "customer churn rate",
                "status": "insufficient",
                "closest": [{"doc_id": "D1", "text": "Total assets $ 364,980"}]}]
    got = rejected_candidates(entries)
    assert len(got) == 1 and got[0]["status"] == "insufficient"

    page = _text(render(_data(CorpusIdentity(["D1"], {"D1": "h"}, "cal", True),
                              entries=entries)))
    assert "customer churn rate" in page
    assert "Surfaced and set aside (1)" in page


def test_the_signature_block_places_certification_with_the_reviewer():
    page = _text(render(_data(CorpusIdentity([], {}, "cal", True))))
    assert "37 CFR 11.18(b)" in page
    assert "rests with that reviewer" in page
