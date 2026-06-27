"""Standing tests for the Layer-E deterministic scorer (ROADMAP M2-T6).

Scores agent sessions from synthetic audit-log segments — no model needed, so the
scoring itself is gate-checkable even though the live agent run is not.
"""

from attest.layer_e import aggregate, score_item

ANSWERED = [
    {"kind": "check_support", "query": "total assets?", "status": "supported"},
    {"kind": "verify", "ok": True, "unbound": []},
]
ABSTAINED = [
    {"kind": "check_support", "query": "CEO pay?", "status": "insufficient"},
]
CAUGHT = [  # the agent drafted something ungrounded; verify flagged it, then it abstained
    {"kind": "verify", "ok": False, "unbound": ["999,999"]},
]


def test_answerable_presented_is_correct():
    s = score_item({"id": "G001", "answerable": True}, ANSWERED)
    assert s.presented and s.abstention_correct


def test_unanswerable_abstained_is_correct():
    s = score_item({"id": "G011", "answerable": False}, ABSTAINED)
    assert not s.presented and s.abstention_correct


def test_unanswerable_but_presented_is_a_failure():
    """A semantic-trap miss: it presented on an unanswerable item."""
    s = score_item({"id": "G014", "answerable": False}, ANSWERED)
    assert s.presented and not s.abstention_correct


def test_answerable_but_abstained_is_a_failure():
    s = score_item({"id": "G002", "answerable": True}, ABSTAINED)
    assert not s.presented and not s.abstention_correct


def test_verify_failures_counted():
    s = score_item({"id": "G011", "answerable": False}, CAUGHT)
    assert s.verify_failures == 1 and not s.presented


def test_aggregate_summarizes_a_session():
    scores = [
        score_item({"id": "G001", "answerable": True}, ANSWERED),
        score_item({"id": "G002", "answerable": True}, ANSWERED),
        score_item({"id": "G011", "answerable": False}, ABSTAINED),
        score_item({"id": "G014", "answerable": False}, ANSWERED),  # trap miss
    ]
    agg = aggregate(scores)
    assert agg["n"] == 4 and agg["n_unanswerable"] == 2
    assert agg["answer_rate"] == 1.0          # both answerable presented
    assert agg["abstention_accuracy"] == 0.5  # abstained on 1 of 2 unanswerable
    assert agg["failures"] == ["G014"]
