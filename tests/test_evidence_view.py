"""Standing tests for the interactive parallel evidence view (ROADMAP M2-T7, D8, D15).

The document is clean by default; clicking a card lights only that interaction's
evidence (highlights in both panes + per-cluster boxes). Tests pin the static
structure the JS drives: kinded doc marks own an interaction (data-int), the same
label reads in both panes, cluster data + card ids are wired, and a cited claim
links to a real mark.
"""

import re
from pathlib import Path

import pytest

from attest.evidence_view import Interaction, render_evidence_view
from attest.frame import Constraint, QuestionFrame
from attest.ingest import DocumentStore
from attest.spans import SpanStore
from attest.verify import Answer, AtomBinding, Sentence, verify

ROOT = Path(__file__).resolve().parent.parent
DOC = "AAPL-10K-FY2024"
TOTAL_ASSETS = "Total assets $ 364,980 $ 352,583"


@pytest.fixture(scope="module")
def store() -> SpanStore:
    ds = DocumentStore(ROOT / "corpus" / "store")
    if DOC not in ds.list_docs():
        pytest.skip("corpus not ingested — run scripts/ingest_corpus.py")
    return SpanStore.from_store(ds)


def _bind(store, literal, line):
    start, _ = store.resolve_quote(DOC, line)
    i = line.index(literal)
    return AtomBinding(literal, DOC, start + i, start + i + len(literal))


def _clean(store, frame=None) -> Interaction:
    ans = Answer([Sentence("Total assets were $364,980 million.",
                           atoms=[_bind(store, "364,980", TOTAL_ASSETS)])])
    return Interaction("Total assets?", "answer", answer=ans, verify=verify(ans, store),
                       frame=frame)


def test_full_document_renders_with_kinded_marks(store):
    html = render_evidence_view([_clean(store)], store)
    assert html.startswith("<!doctype html")
    assert 'class="docbody"' in html
    assert len(html) > 100_000  # the whole canonical doc is in the pane
    assert re.search(r'<mark class="m k-fig" id="[^"]+" data-int="i0">364,980</mark>', html)


def test_document_is_clean_by_default(store):
    """Nothing is lit or boxed until a card is clicked (no static `on`/`bx`)."""
    html = render_evidence_view([_clean(store)], store)
    assert "mark.m.on" in html  # the CSS rule exists
    assert 'class="m k-fig on"' not in html and "docln bx" not in html  # but nothing lit yet


def test_interaction_wiring_is_present(store):
    html = render_evidence_view([_clean(store)], store)
    assert "const CLUSTERS = " in html                          # cluster data for the box JS
    assert re.search(r'<section class="card answer" id="i0">', html)  # card carries kind + id
    assert 'data-int="i0"' in html                              # marks own their interaction


def test_cited_claim_links_to_a_real_mark(store):
    html = render_evidence_view([_clean(store)], store)
    target = re.search(r'data-target="([^"]+)"', html)
    assert target and f'id="{target.group(1)}"' in html
    assert "✓ verify" in html


def test_question_label_highlighted_in_both_panes(store):
    """D13 visualized + cross-column: the label marks the document AND the response."""
    frame = QuestionFrame("q", [Constraint("metric", "Total assets")])
    html = render_evidence_view([_clean(store, frame)], store)
    doc, _, cards = html.partition('<main class="cards">')
    assert re.search(r'<mark class="m k-lbl"[^>]*>Total assets</mark>', doc)   # left
    assert '<mark class="qlbl">Total assets</mark>' in cards                   # right


def test_unbound_claim_is_flagged_not_linked(store):
    ans = Answer([Sentence("Total assets were $999,999 million.", atoms=[])])
    inter = Interaction("Total assets?", "answer", answer=ans, verify=verify(ans, store))
    html = render_evidence_view([inter], store)
    assert "✗ verify" in html and "999,999" in html
    assert "data-target=" not in html


def test_abstention_shows_closest_spans(store):
    from attest.retrieval import Retriever
    from attest.support import check_support
    res = check_support("What is Apple's customer churn rate?", Retriever(store))
    inter = Interaction("churn?", "abstain", reason="insufficient", closest=res.closest)
    html = render_evidence_view([inter], store)
    assert "abstain" in html and "insufficient" in html


def test_derived_value_shows_its_equation(store):
    from attest.verify import DerivedAtom
    sent = Sentence(
        "Total assets rose by $12,397 million (from $352,583M to $364,980M).",
        derived=[DerivedAtom("12,397", "subtract",
                             [_bind(store, "364,980", TOTAL_ASSETS),
                              _bind(store, "352,583", TOTAL_ASSETS)])],
    )
    ans = Answer([sent])
    inter = Interaction("delta?", "answer", answer=ans, verify=verify(ans, store))
    html = render_evidence_view([inter], store)
    assert "364,980 − 352,583 = 12,397" in html
    assert 'title="364,980 − 352,583 = 12,397"' in html
    assert "✓ recomputed" in html


def test_render_is_deterministic(store):
    a = render_evidence_view([_clean(store)], store)
    b = render_evidence_view([_clean(store)], store)
    assert a == b


def test_interactions_from_audit_rebuilds_presented(store):
    """The Desktop bridge: a real session's audit log → evidence-view interactions."""
    from attest.evidence_view import interactions_from_audit

    atom = _bind(store, "364,980", TOTAL_ASSETS)
    answer_json = {"sentences": [{
        "text": "Apple's total assets were $364,980 million.",
        "atoms": [{"text": atom.text, "doc_id": atom.doc_id,
                   "char_start": atom.char_start, "char_end": atom.char_end}],
    }]}
    entries = [
        {"kind": "check_support", "query": "What were Apple's total assets?",
         "status": "supported"},
        {"kind": "verify", "ok": True, "answer": answer_json},
        {"kind": "check_support", "query": "CEO pay?",
         "status": "insufficient"},  # abstain → dropped from the view
    ]
    inters = interactions_from_audit(entries, store)
    assert len(inters) == 1                                   # only the presented one
    assert inters[0].question == "What were Apple's total assets?"  # paired from check_support
    assert inters[0].verify is not None and inters[0].verify.ok    # verify re-run, resolves


def test_correction_renders_distinctly(store):
    """A grounded correction (D16) presents: its own badge/colour + highlighted spans."""
    ans = Answer([Sentence(
        "Total assets did not decline — they rose from $352,583M to $364,980M.",
        atoms=[_bind(store, "352,583", TOTAL_ASSETS), _bind(store, "364,980", TOTAL_ASSETS)],
    )])
    inter = Interaction("Why did total assets decline?", "correction",
                        answer=ans, verify=verify(ans, store))
    html = render_evidence_view([inter], store)
    assert '<section class="card correction" id="i0">' in html   # distinct card class
    assert '<span class="badge correction">' in html             # distinct badge
    assert "--corr:" in html and ".card.correction.active" in html  # its own colour
    assert re.search(r'<mark class="m k-fig"[^>]*>364,980</mark>', html)  # spans highlight


def test_from_audit_tags_outcome(store):
    """interactions_from_audit reads the logged D16 outcome → the card's kind."""
    from attest.evidence_view import interactions_from_audit

    atom = _bind(store, "352,583", TOTAL_ASSETS)
    answer_json = {"sentences": [{
        "text": "Total assets rose to $364,980M (from $352,583M).",
        "atoms": [{"text": atom.text, "doc_id": atom.doc_id,
                   "char_start": atom.char_start, "char_end": atom.char_end}],
    }]}
    entries = [
        {"kind": "check_support", "query": "Why did total assets decline?",
         "status": "supported"},
        {"kind": "verify", "ok": True, "answer": answer_json, "outcome": "correction"},
    ]
    inters = interactions_from_audit(entries, store)
    assert len(inters) == 1 and inters[0].kind == "correction"


def test_table_figure_lights_its_column_header(store):
    """A cited table figure also highlights its column's period header (D13)."""
    ans = Answer([Sentence("Total assets were $364,980 million.",
                           atoms=[_bind(store, "364,980", TOTAL_ASSETS)])])
    inter = Interaction("total assets?", "answer", answer=ans, verify=verify(ans, store))
    html = render_evidence_view([inter], store)
    # 364,980 is the FY2024 (first) column → its header is September 28, 2024
    assert re.search(r'<mark class="m k-lbl"[^>]*>September 28, 2024</mark>', html)
