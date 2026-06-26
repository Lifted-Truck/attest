"""Standing tests for the evidence-view renderer (ROADMAP M2-T7, D8).

AC: a cited claim hyperlinks to its exact highlighted span; an unbound claim is
shown flagged (never silently linked); the render is deterministic and
self-contained (no server/network).
"""

import re
from pathlib import Path

import pytest

from attest.evidence_view import Interaction, render_evidence_view
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


def _clean(store) -> Interaction:
    ans = Answer([Sentence("Total assets were $364,980 million.",
                           atoms=[_bind(store, "364,980", TOTAL_ASSETS)])])
    return Interaction("Total assets?", "answer", answer=ans, verify=verify(ans, store))


def test_cited_claim_links_to_its_highlighted_span(store):
    html = render_evidence_view([_clean(store)], store)
    assert html.startswith("<!doctype html")
    assert "<mark>364,980</mark>" in html              # highlighted in the source pane
    target = re.search(r'data-target="([^"]+)"', html)  # the clickable chip
    assert target, "no click-to-source chip rendered"
    assert f'id="{target.group(1)}"' in html            # ...points to a real span element
    assert "✓ verify" in html


def test_unbound_claim_is_flagged_not_linked(store):
    ans = Answer([Sentence("Total assets were $999,999 million.", atoms=[])])
    inter = Interaction("Total assets?", "answer", answer=ans, verify=verify(ans, store))
    html = render_evidence_view([inter], store)
    assert "✗ verify" in html and "999,999" in html
    assert 'data-target=' not in html  # nothing to link — the figure is unbound


def test_abstention_shows_closest_spans(store):
    from attest.retrieval import Retriever
    from attest.support import check_support
    res = check_support("What is Apple's customer churn rate?", Retriever(store))
    inter = Interaction("churn?", "abstain", reason="insufficient", closest=res.closest)
    html = render_evidence_view([inter], store)
    assert "abstain" in html and "insufficient" in html


def test_render_is_deterministic(store):
    a = render_evidence_view([_clean(store)], store)
    b = render_evidence_view([_clean(store)], store)
    assert a == b
