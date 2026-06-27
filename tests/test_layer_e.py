"""Standing tests for the Layer-E deterministic scorer (ROADMAP M2-T6).

Scores agent sessions from synthetic audit-log segments — no model needed, so the
scoring itself is gate-checkable even though the live agent run is not.
"""

from attest.layer_e import (
    aggregate,
    brier_score,
    claims_and_spans,
    judge_entailment,
    reliability,
    score_item,
)

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


# --- entailment judge (model call injected as a fake) ---


def test_judge_yes_means_entails():
    v = judge_entailment("Total assets were $364,980M", "Total assets $ 364,980 $ 352,583",
                         ask=lambda _p: "YES — the line states it.")
    assert v.entails


def test_judge_no_or_ambiguous_defaults_to_not_entailed():
    assert not judge_entailment("x", "y", ask=lambda _p: "NO").entails
    assert not judge_entailment("x", "y", ask=lambda _p: "").entails          # empty → NO
    assert not judge_entailment("x", "y", ask=lambda _p: "maybe?").entails     # unclear → NO


def test_judge_prompt_carries_claim_and_span():
    seen = {}
    judge_entailment("CLAIM-A", "SPAN-B", ask=lambda p: seen.setdefault("p", p) and "" or "YES")
    assert "CLAIM-A" in seen["p"] and "SPAN-B" in seen["p"]


def test_claims_and_spans_extracts_from_verify_record():
    payload = {"answer": {"sentences": [
        {"text": "Total assets were $364,980M.",
         "atoms": [{"doc_id": "D", "char_start": 0, "char_end": 7}]},
        {"text": "no atoms here", "atoms": []},
    ]}}
    got = list(claims_and_spans(payload, get_span=lambda d, s, e: f"<{s}:{e}>"))
    assert got == [("Total assets were $364,980M.", ["<0:7>"])]  # the no-atom sentence is skipped


# --- calibration (pure) ---


def test_brier_perfect_and_worst():
    assert brier_score([(1.0, True), (0.0, False)]) == 0.0   # perfectly calibrated
    assert brier_score([(1.0, False), (0.0, True)]) == 1.0   # confidently wrong
    assert brier_score([]) is None


def test_reliability_buckets():
    pairs = [(0.9, True), (0.95, True), (0.1, False), (0.2, False)]
    buckets = reliability(pairs, bins=5)
    top = next(b for b in buckets if b["bucket"] == "0.8-1.0")
    assert top["n"] == 2 and top["accuracy"] == 1.0
