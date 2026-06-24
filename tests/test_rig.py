"""Standing test for the M0 gate (ROADMAP M0-T4, brief §2).

The audition rig must clear the gate on the golden seed every time, so the M0
proof can't silently rot. This runs the rig's own scoring and asserts the gate
thresholds: citation precision ≥ 0.9 (D5), hallucination = 0, abstention
accuracy = 1.0 on unanswerable items, and no false abstentions.
"""

import json

import attest_rig as rig
import pytest


@pytest.fixture(scope="module")
def report():
    if not rig.MANIFEST.exists():
        pytest.skip("toy corpus not built — run scripts/build_toy_corpus.py")
    bm25 = rig.BM25(rig.load_spans())
    golden = json.loads(rig.GOLDEN.read_text(encoding="utf-8"))["items"]
    return [(item, rig.run_item(item, bm25)) for item in golden]


def test_abstains_on_every_unanswerable_item(report):
    """The strongest selling point: 100% deterministic abstention (I2)."""
    for item, o in report:
        if not item["answerable"]:
            assert o.abstained, f"{item['id']} should abstain but answered"


def test_no_false_abstentions(report):
    for item, o in report:
        if item["answerable"]:
            assert not o.abstained, f"{item['id']} is answerable but the rig abstained"


def test_full_citation_recall_on_answerable(report):
    """Every supporting operand resolves into a cited span."""
    for item, o in report:
        if item["answerable"]:
            missing = set(o.evidence) - set(o.covered)
            assert not missing, f"{item['id']} missing evidence in citations: {missing}"


def test_no_hallucinated_assertions(report):
    """verify (I1): the rig only asserts values present in a cited span."""
    by_id = {s.span_id: s for s in rig.load_spans()}
    for item, o in report:
        if item["answerable"]:
            cited_text = "\n".join(by_id[c].text for c in o.cited)
            for value in o.asserted:
                assert value in cited_text, f"{item['id']} asserted {value!r} with no cited span"


def test_m0_gate_passes(report):
    precisions = []
    for item, o in report:
        if item["answerable"] and o.cited:
            by_id = {s.span_id: s for s in rig.load_spans()}
            n_supporting = sum(1 for c in o.cited if rig.supports(by_id[c].text, o.evidence))
            precisions.append(n_supporting / len(o.cited))
    citation_precision = sum(precisions) / len(precisions)
    assert citation_precision >= 0.90, f"citation precision {citation_precision:.2%} < 90% (D5)"
