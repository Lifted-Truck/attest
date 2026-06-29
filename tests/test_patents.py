"""Standing tests for the patent claim model (PE-1, first increment).

Deterministic structural parsing over the shared canonical text — no model. Uses a
synthetic sample patent so it is hermetic and free of confidentiality/copyright.
"""

from pathlib import Path

from attest.ingest import DocumentStore
from attest.ingest.files import ingest_paths
from attest.patents import parse_claims
from attest.spans import SpanStore

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "corpus" / "samples" / "sample_patent.txt"


def _text() -> str:
    return SAMPLE.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_parses_claims_with_dependency():
    claims = parse_claims(_text())
    assert [c.number for c in claims] == [1, 2, 3, 4, 5]
    assert [c.kind for c in claims] == [
        "independent", "dependent", "dependent", "independent", "dependent",
    ]
    assert [c.depends_on for c in claims] == [None, 1, 2, None, 4]


def test_claim_offsets_are_self_addressable():
    text = _text()
    claims = parse_claims(text)
    for c in claims:
        assert text[c.char_start:c.char_end] == c.text     # offsets are exact
        assert c.text.startswith(f"{c.number}.")           # starts at the claim number


def test_claim_spans_resolve_through_the_span_store(tmp_path):
    """Builds on the shared engine: each claim is a real, hash-verified span (I3)."""
    store_dir = tmp_path / "store"
    ingest_paths([str(SAMPLE)], store_dir, kind="patent")
    store = SpanStore.from_store(DocumentStore(store_dir))
    doc = SAMPLE.stem
    text = store.get_document(doc)
    for c in parse_claims(text):
        assert store.get_span(doc, c.char_start, c.char_end) == c.text


def test_no_claims_section_returns_empty():
    assert parse_claims("A document with no claims section at all.") == []


def test_decompose_independent_claim_into_limitations():
    from attest.patents import decompose_claim
    claims = parse_claims(_text())
    lims = decompose_claim(claims[0])               # claim 1: comprising + 2 semicolons
    assert [lim.text for lim in lims] == [
        "a housing",
        "a sprocket coupled to the housing",
        "a controller configured to rotate the sprocket based on a measured temperature",
    ]
    text = _text()
    for lim in lims:                                # each limitation is self-addressable
        assert text[lim.char_start:lim.char_end] == lim.text


def test_dependent_wherein_is_one_limitation():
    from attest.patents import decompose_claim
    claims = parse_claims(_text())
    lims = decompose_claim(claims[1])               # "...wherein the sprocket comprises titanium"
    assert len(lims) == 1
    assert lims[0].text == "the sprocket comprises titanium"


def test_limitations_resolve_through_the_span_store(tmp_path):
    from attest.patents import decompose_claim
    store_dir = tmp_path / "store"
    ingest_paths([str(SAMPLE)], store_dir, kind="patent")
    store = SpanStore.from_store(DocumentStore(store_dir))
    doc = SAMPLE.stem
    c1 = parse_claims(store.get_document(doc))[0]
    for lim in decompose_claim(c1):
        assert store.get_span(doc, lim.char_start, lim.char_end) == lim.text


def test_parse_paragraphs_uses_native_numbering():
    from attest.patents import parse_paragraphs
    paras = parse_paragraphs(_text())                       # synthetic has [0001]–[0006]
    assert [p.label for p in paras] == ["[0001]", "[0002]", "[0003]",
                                        "[0004]", "[0005]", "[0006]"]
    text = _text()
    for p in paras:                                         # each is self-addressable
        assert text[p.char_start:p.char_end] == p.text
    assert paras[0].text.startswith("[0001]")
    assert "claimed" not in " ".join(p.text for p in paras)  # claims excluded


def test_paragraphs_resolve_through_the_span_store(tmp_path):
    from attest.patents import parse_paragraphs
    store_dir = tmp_path / "store"
    ingest_paths([str(SAMPLE)], store_dir, kind="patent")
    store = SpanStore.from_store(DocumentStore(store_dir))
    doc = SAMPLE.stem
    for p in parse_paragraphs(store.get_document(doc)):
        assert store.get_span(doc, p.char_start, p.char_end) == p.text


def test_support_mapping_links_limitation_to_spec_paragraph():
    """PE-3: claim 2's titanium limitation maps to the spec paragraph that describes it."""
    from attest.patents import map_claim_support, parse_paragraphs
    text = _text()
    claims = parse_claims(text)
    paras = parse_paragraphs(text)
    mapping = dict((lim.text, edges)
                   for lim, edges in map_claim_support(claims[1], paras, SAMPLE.stem))
    edges = mapping["the sprocket comprises titanium"]
    assert edges, "expected support to be located"
    assert edges[0].paragraph_label == "[0005]"          # the titanium/aluminum paragraph
    assert edges[0].edge_type == "CLAIM_LIMITATION→SPEC_SUPPORT"


def test_support_edges_are_addressable(tmp_path):
    from attest.patents import map_claim_support, parse_paragraphs
    store_dir = tmp_path / "store"
    ingest_paths([str(SAMPLE)], store_dir, kind="patent")
    store = SpanStore.from_store(DocumentStore(store_dir))
    doc = SAMPLE.stem
    text = store.get_document(doc)
    c1 = parse_claims(text)[0]
    for _lim, edges in map_claim_support(c1, parse_paragraphs(text), doc):
        for e in edges:                                  # each edge points at a real span
            assert store.get_span(doc, e.char_start, e.char_end)


def test_dependency_integrity_clean_patent_has_no_issues():
    from attest.patents import check_dependencies
    assert check_dependencies(parse_claims(_text())) == []   # synthetic is well-formed


def test_dependency_integrity_flags_missing_and_forward_refs():
    from attest.patents import Claim, check_dependencies
    claims = [
        Claim(1, "1. A device.", 0, 12, "independent", None),
        Claim(2, "2. The device of claim 9, …", 13, 40, "dependent", 9),    # missing
        Claim(3, "3. The device of claim 5, …", 41, 68, "dependent", 5),    # forward (5 exists)
        Claim(5, "5. The device of claim 1, …", 69, 96, "dependent", 1),    # ok
    ]
    issues = check_dependencies(claims)
    assert {i.claim_number for i in issues} == {2, 3}
    assert "does not exist" in next(i.message for i in issues if i.claim_number == 2)
    assert "not an earlier claim" in next(i.message for i in issues if i.claim_number == 3)
