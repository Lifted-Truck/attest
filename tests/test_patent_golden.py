"""Standing tests for the patent golden set (PE-5) — US5447630A.

The engagement store is gitignored (local-only), so these skip when it is absent
(CI) and run wherever the corpus is ingested. Same discipline as the EDGAR golden:
quotes must resolve (D7), the outcome taxonomy must map (D16/D22), the PE-3
support expectations must hold, and the D20 calibrator must run on the set.
"""

import json
from pathlib import Path

import pytest

from attest.ingest import DocumentStore
from attest.layer_e import expected_outcome
from attest.retrieval import Retriever
from attest.spans import SpanStore

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "golden_patent.json"
STORE = ROOT / "corpus" / "engagements" / "US5447630A" / "store"
DOC = "US5447630A"


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def store() -> SpanStore:
    ds = DocumentStore(STORE)
    if DOC not in ds.list_docs():
        pytest.skip("engagement corpus not ingested (local-only; see desktop_setup §5)")
    return SpanStore.from_store(ds)


def test_taxonomy_covers_all_five_outcomes(golden):
    """D16/D22: the set exercises every outcome class, incl. refuse-to-adjudicate."""
    classes = [expected_outcome(it) for it in golden["items"]]
    counts = {c: classes.count(c) for c in set(classes)}
    assert counts["answer"] >= 8
    assert counts["abstain"] >= 5
    assert counts["refuse"] >= 5          # the cardinal-rule negatives (D10)
    assert counts["correction"] >= 2
    assert counts["partial"] >= 1


def test_supporting_quotes_resolve(golden, store):
    """D7 for the patent golden: every quote is real; unique ones resolve 1:1."""
    text = store.get_document(DOC)
    checked = 0
    for it in golden["items"]:
        for sup in it.get("supporting", []):
            n = text.count(sup["verbatim_quote"])
            if sup["resolution"] == "unique":
                assert n == 1, f"{it['id']}: expected unique, found {n}×"
            else:
                assert n >= 1, f"{it['id']}: quote not found"
            checked += 1
    assert checked >= 10


def test_support_expectations_hold(golden, store):
    """PE-3 golden: each named claim limitation maps to the expected spec paragraph."""
    from attest.patents import decompose_claim, map_claim_support, parse_claims, parse_paragraphs

    text = store.get_document(DOC)
    claims = {c.number: c for c in parse_claims(text)}
    paragraphs = parse_paragraphs(text)
    for exp in golden["support_expectations"]:
        claim = claims[exp["claim"]]
        lims = [lim for lim in decompose_claim(claim) if exp["limitation_contains"] in lim.text]
        assert lims, f"{exp['id']}: no limitation contains {exp['limitation_contains']!r}"
        mapping = dict(
            (lim.index, edges) for lim, edges in map_claim_support(claim, paragraphs, DOC, k=3)
        )
        edges = mapping[lims[0].index]
        para_texts = [store.get_span(DOC, e.char_start, e.char_end) for e in edges]
        assert any(exp["expected_paragraph_contains"] in p for p in para_texts), (
            f"{exp['id']}: expected paragraph not in top-3 support"
        )


def test_calibrator_runs_on_the_patent_golden(golden, store):
    """D20 on the patent set: the calibrator fits a floor and reports the separation
    honestly (overlap allowed — that is a finding about BM25 here, not a failure)."""
    from attest.support import calibrate_threshold

    c = calibrate_threshold(golden["items"], Retriever(store))
    assert 0.0 < c.threshold < 30.0
    assert c.n_present >= 8 and c.n_absent >= 5
    assert c.excluded >= 8                # corrections/partials/refusals are not floor data
