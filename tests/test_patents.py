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


# --- PE-4: front matter + effective filing + regime flag ---


def test_front_matter_parses_the_synthetic_fixture():
    from attest.patents import effective_filing, parse_front_matter, regime_flag
    fm = parse_front_matter(_text())
    assert fm.application_number == "17/000,000"
    assert fm.filed == "Mar. 15, 2021"
    assert any("Jane Smith" in i for i in fm.inventors)
    assert fm.priority_claims and "62/900,000" in fm.priority_claims[0]
    # effective filing = the PROVISIONAL's date (earlier than filing)
    src, d = effective_filing(fm)
    assert d == (2020, 3, 20) and "62/900,000" in src
    rf = regime_flag(fm)
    assert rf["flag"] == "AIA" and rf["effective_filing_date"] == "2020-03-20"
    assert "professional determination" in rf["note"]     # the D10 boundary, stated


def test_front_matter_parses_the_real_patent(tmp_path):
    import pathlib

    from attest.patents import parse_front_matter, regime_flag
    real = pathlib.Path("corpus/engagements/US5447630A/US5447630A.txt")
    if not real.exists():
        import pytest as _pytest
        _pytest.skip("engagement corpus not present (local-only)")
    fm = parse_front_matter(real.read_text(encoding="utf-8"))
    assert fm.filed == "Apr. 28, 1993"
    assert fm.date_of_patent == "Sep. 5, 1995"
    assert fm.inventors == ["John M. Rummler"]
    assert fm.application_number == "08/053,402"
    rf = regime_flag(fm)
    assert rf["flag"] == "pre-AIA" and rf["effective_filing_date"] == "1993-04-28"


# --- RT-4 / PE-1 remainder: figures + references + reference numerals ---


def test_parse_figures_reads_the_drawings_captions():
    from attest.patents import parse_figures
    text = _text()
    figs = parse_figures(text)
    assert [f.label for f in figs] == ["FIG. 1", "FIG. 2"]
    assert [f.number for f in figs] == ["1", "2"]
    assert figs[0].description.startswith("FIG. 1 is a perspective view")
    assert "cross-sectional view" in figs[1].description
    for f in figs:                                       # each caption self-addresses
        assert text[f.char_start:f.char_end] == f.description


def test_figure_references_carry_offsets():
    from attest.patents import figure_references
    text = _text()
    refs = figure_references(text)
    assert {r.number for r in refs} == {"1", "2"}        # FIG.1 (×2) + FIG.2
    assert sum(r.number == "1" for r in refs) == 2       # caption + detailed-description
    for r in refs:                                       # the offset points at "FIG"
        assert text[r.char_start:].upper().startswith("FIG")


def test_reference_numerals_map_number_to_element():
    from attest.patents import reference_numerals
    nums = {n.number: n.element for n in reference_numerals(_text())}
    assert set(nums) == {100, 12, 14, 10}                # the four ≥10 numerals
    assert "device" in nums[100] and "housing" in nums[10]
    assert "sprocket" in nums[12] and "controller" in nums[14]


def test_reference_numerals_ignore_claim_noise_without_a_magnitude_floor():
    """Claim references ('of claim 1/2/4') are excluded STRUCTURALLY — by scanning the
    specification only — not by a minimum-numeral guess. The fixture's claims recite
    "of claim 1/2/4", none of which may appear as numerals."""
    from attest.patents import parse_claims, reference_numerals
    text = _text()
    nums = {n.number: n.element for n in reference_numerals(text)}
    claim_starts = {c.char_start for c in parse_claims(text)}
    assert claim_starts, "fixture must have claims for this test to mean anything"
    for n in reference_numerals(text):                   # nothing sourced from the claims
        assert n.char_start < min(claim_starts)
    assert "claim" not in " ".join(nums.values())


def test_single_digit_reference_numerals_are_kept():
    """Regression (2026-07-08): a MIN_NUMERAL=10 floor silently deleted five REAL
    numerals from US5447630A ("bathtub or shower 1, toilet 2, … dishwasher 4 and
    clothes washer 5" — the FIG. 1 sources). "Numerals start at 10" is a folk rule,
    not a spec. Over-filtering deletes evidence invisibly; that is the worse failure."""
    import pathlib
    real = pathlib.Path("corpus/engagements/US5447630A/US5447630A.txt")
    if not real.exists():
        import pytest as _pytest
        _pytest.skip("engagement corpus not present (local-only)")
    from attest.patents import reference_numerals
    nums = {n.number: n.element for n in reference_numerals(real.read_text(encoding="utf-8"))}
    assert "bathtub" in nums[1] and "toilet" in nums[2]
    assert "dishwasher" in nums[4] and "clothes washer" in nums[5]


def test_reference_numerals_reject_decimals_and_quantities():
    """A decimal ("measured as 0.24 mg/l") is not numeral 0; a quantity with a unit
    ("400 W", "60 degrees") is a measurement, not a pointer into a drawing."""
    from attest.patents import reference_numerals
    sample = ("The chlorine residual has been measured as 0.24 mg/l in the tank 42. "
              "The magnetron 44 draws 400 W and the chamber holds 60 degrees.")
    nums = {n.number: n.element for n in reference_numerals(sample)}
    assert 0 not in nums                                # the decimal
    assert 400 not in nums and 60 not in nums           # quantities carrying units
    assert "tank" in nums[42] and "magnetron" in nums[44]


def test_figure_and_numeral_spans_resolve_through_the_span_store(tmp_path):
    from attest.patents import parse_figures, reference_numerals
    store_dir = tmp_path / "store"
    ingest_paths([str(SAMPLE)], store_dir, kind="patent")
    store = SpanStore.from_store(DocumentStore(store_dir))
    doc = SAMPLE.stem
    text = store.get_document(doc)
    for f in parse_figures(text):
        assert store.get_span(doc, f.char_start, f.char_end) == f.description
    for n in reference_numerals(text):                   # the first-mention span is real
        assert store.get_span(doc, n.char_start, n.char_end)


def test_figures_validate_on_the_real_patent():
    """Sanity on US5447630A: the drawings block yields its figures, the ≥10 numerals
    include the known-good bindings (locate-only; not an exhaustive gate)."""
    import pathlib
    real = pathlib.Path("corpus/engagements/US5447630A/US5447630A.txt")
    if not real.exists():
        import pytest as _pytest
        _pytest.skip("engagement corpus not present (local-only)")
    from attest.patents import parse_figures, reference_numerals
    t = real.read_text(encoding="utf-8")
    labels = [f.label for f in parse_figures(t)]
    assert labels == ["FIG. 1", "FIG. 2", "FIG. 4", "FIG. 5", "FIG. 6"]  # clean block
    nums = {n.number: n.element for n in reference_numerals(t)}
    assert "microwave reactor chamber" in nums[12]
    assert "ceramic filter material" in nums[38]
    assert "necked portion" in nums[89]
