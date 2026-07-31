"""Standing tests for per-corpus support-floor calibration (RT-9, D44)."""

from __future__ import annotations

import pytest

from cairn.calibration import CalibrationRecord, corpus_hash, resolve, write
from cairn.ingest.document import make_document
from cairn.ingest.store import DocumentStore

pytestmark = pytest.mark.layer0


def _store(tmp_path, text="Total assets $ 364,980 as of September 28, 2024."):
    s = DocumentStore(tmp_path / "store")
    s.write(make_document("D1", text))
    return s


def _record(store, threshold=22.0, date="2026-07-28"):
    ids = store.list_docs()
    return CalibrationRecord(
        threshold=threshold, corpus_id="test", doc_ids=ids,
        corpus_hash=corpus_hash(ids, [store.load(d).content_hash for d in ids]),
        calibrated_on=date, method="golden-gap", n_present=10, n_absent=3)


def test_an_uncalibrated_store_is_named_as_such(tmp_path):
    """RT-9: the support floor is a BM25 score, which does not transfer between corpora.
    Measured on US8046721B2: "how is the device unlocked" — the patent's whole subject —
    scores 4.56 against the EDGAR floor of 15.0, so Cairn abstains on an answerable
    question. That is a FALSE ABSTENTION, the failure that looks like diligence. It may
    still happen; it may not happen silently."""
    _store(tmp_path)
    choice = resolve(tmp_path / "store", default=15.0)
    assert choice.threshold == 15.0          # still usable — a warning, not a refusal
    assert choice.calibrated is False
    assert "UNCALIBRATED" in choice.warning
    assert "FALSE ABSTENTION" in choice.warning


def test_a_calibrated_store_uses_its_own_floor_without_warning(tmp_path):
    store = _store(tmp_path)
    write(tmp_path / "store", _record(store, threshold=22.0))
    choice = resolve(tmp_path / "store", default=15.0,
                     live_doc_ids=store.list_docs(),
                     live_hashes=[store.load(d).content_hash for d in store.list_docs()])
    assert (choice.threshold, choice.calibrated, choice.warning) == (22.0, True, None)


def test_calibration_goes_stale_when_the_corpus_changes(tmp_path):
    """A floor is fitted to a specific corpus, so editing or adding a document
    invalidates the separation it was fitted to — the same reasoning as I3's content
    hash, applied to a fitted value rather than to text."""
    store = _store(tmp_path)
    write(tmp_path / "store", _record(store))
    store.write(make_document("D2", "An entirely new document changes the corpus."))

    ids = store.list_docs()
    choice = resolve(tmp_path / "store", default=15.0, live_doc_ids=ids,
                     live_hashes=[store.load(d).content_hash for d in ids])
    assert choice.calibrated is False
    assert "STALE CALIBRATION" in choice.warning
    assert choice.threshold == 22.0, "the stale floor is still reported, not silently swapped"


def test_corpus_hash_is_order_independent_but_content_sensitive(tmp_path):
    a = corpus_hash(["x", "y"], ["h1", "h2"])
    assert a == corpus_hash(["y", "x"], ["h2", "h1"])     # directory order must not matter
    assert a != corpus_hash(["x", "y"], ["h1", "CHANGED"])


def test_the_warning_reaches_the_audit_record_and_survives_replay(tmp_path):
    """RT-9 + I6: an abstention taken under a foreign floor must keep saying so in the
    log, and replay must not launder the caveat away."""
    from cairn.retrieval import Retriever
    from cairn.session import replay_support, support_record
    from cairn.spans import SpanStore
    from cairn.support import check_support

    store = _store(tmp_path)
    retriever = Retriever(SpanStore.from_store(store))
    warning = "UNCALIBRATED STORE: applying a support floor of 15.0 …"
    rec = support_record("what were total assets",
                         check_support("what were total assets", retriever, threshold=15.0),
                         threshold=15.0, retrieval=retriever.method,
                         calibration_warning=warning)
    assert rec["calibration_warning"] == warning
    assert replay_support(rec, retriever) == rec          # byte-identical, caveat intact

    clean = support_record("q", check_support("q", retriever, threshold=15.0),
                           threshold=15.0, retrieval=retriever.method)
    assert "calibration_warning" not in clean, "a calibrated record stays byte-unchanged"
    assert replay_support(clean, retriever) == clean


def test_an_explicit_threshold_overrides_the_store_and_says_so(tmp_path):
    """RT-9: the store's record must not silently override a caller's stated intent —
    that is the same silent-override defect the mechanism exists to remove. An explicit
    floor wins, and is labelled an override rather than passed off as calibrated."""
    from cairn.tools import default_registry
    store = _store(tmp_path)
    write(tmp_path / "store", _record(store, threshold=22.0))

    reg = default_registry(tmp_path / "store")                      # no override
    rec = reg["check_support"].handler({"query": "total assets"})
    assert rec["provenance"]["threshold"] == 22.0
    assert "calibration_warning" not in rec

    reg = default_registry(tmp_path / "store", support_threshold=5.0)
    rec = reg["check_support"].handler({"query": "total assets"})
    assert rec["provenance"]["threshold"] == 5.0, "the caller's floor must win"
    assert "EXPLICIT OVERRIDE" in rec["calibration_warning"]
