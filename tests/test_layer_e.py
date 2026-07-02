"""Standing tests for the Layer-E deterministic scorer (ROADMAP M2-T6).

Scores agent sessions from synthetic audit-log segments — no model needed, so the
scoring itself is gate-checkable even though the live agent run is not.
"""

from attest.layer_e import (
    aggregate,
    brier_score,
    claims_and_spans,
    expected_outcome,
    judge_entailment,
    judge_refutes_premise,
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

# golden-item shapes (subset of fields the scorer reads)
I_ANSWER = {"id": "G001", "answerable": True}
I_ABSTAIN = {"id": "G011", "answerable": False, "expected_behavior": "abstain"}
I_CORRECTION = {"id": "G020", "answerable": False, "expected_behavior": "reject-false-premise"}
I_PARTIAL = {"id": "G016", "answerable": False, "expected_behavior": "partial-abstain"}


def test_expected_outcome_taxonomy():
    assert expected_outcome(I_ANSWER) == "answer"
    assert expected_outcome(I_ABSTAIN) == "abstain"
    assert expected_outcome(I_CORRECTION) == "correction"
    assert expected_outcome(I_PARTIAL) == "partial"


def test_answer_presented_is_correct():
    s = score_item(I_ANSWER, ANSWERED)
    assert s.presented and s.decision_correct and s.expected == "answer"


def test_abstain_silent_is_correct():
    s = score_item(I_ABSTAIN, ABSTAINED)
    assert not s.presented and s.decision_correct


def test_grounded_correction_must_present():
    """A false-premise item is RIGHT to present (a grounded refutation), not abstain."""
    presented = score_item(I_CORRECTION, ANSWERED)
    assert presented.presented and presented.decision_correct      # presented → correct
    silent = score_item(I_CORRECTION, ABSTAINED)
    assert not silent.presented and not silent.decision_correct    # silent → wrong


def test_partial_must_present():
    assert score_item(I_PARTIAL, ANSWERED).decision_correct
    assert not score_item(I_PARTIAL, ABSTAINED).decision_correct


def test_answer_but_abstained_is_a_failure():
    s = score_item(I_ANSWER, ABSTAINED)
    assert not s.presented and not s.decision_correct


def test_verify_failures_counted():
    s = score_item(I_ABSTAIN, CAUGHT)
    assert s.verify_failures == 1 and not s.presented


def test_aggregate_summarizes_by_class():
    scores = [
        score_item(I_ANSWER, ANSWERED),
        score_item({"id": "G002", "answerable": True}, ANSWERED),
        score_item(I_ABSTAIN, ABSTAINED),
        score_item(I_CORRECTION, ANSWERED),    # correctly presents a correction
        score_item(I_PARTIAL, ABSTAINED),      # wrongly stayed silent
    ]
    agg = aggregate(scores)
    assert agg["n"] == 5
    assert agg["by_class"] == {"answer": 2, "abstain": 1, "correction": 1, "partial": 1,
                               "refuse": 0}
    assert agg["answer_rate"] == 1.0
    assert agg["abstention_accuracy"] == 1.0
    assert agg["correction_rate"] == 1.0       # G020 presented its correction
    assert agg["partial_rate"] == 0.0          # G016 wrongly abstained
    assert agg["failures"] == ["G016"]


# --- entailment judge (model call injected as a fake) ---


def test_judge_yes_means_supported():
    v = judge_entailment("Total assets were $364,980M", "Total assets $ 364,980 $ 352,583",
                         ask=lambda _p: "YES — the line states it.")
    assert v.yes


def test_judge_no_or_ambiguous_defaults_to_no():
    assert not judge_entailment("x", "y", ask=lambda _p: "NO").yes
    assert not judge_entailment("x", "y", ask=lambda _p: "").yes          # empty → NO
    assert not judge_entailment("x", "y", ask=lambda _p: "maybe?").yes     # unclear → NO


def test_refutes_premise_judge():
    yes = judge_refutes_premise("Why did assets decline?", "They did not decline; they rose.",
                                ask=lambda p: "YES" if "decline" in p else "NO")
    assert yes.yes
    no = judge_refutes_premise("Why did assets decline?", "Assets fell by $X.",
                               ask=lambda _p: "NO, it accepts the premise")
    assert not no.yes


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


# --- refuse-to-adjudicate as a first-class outcome (D22) ---

I_REFUSE = {"id": "P001", "answerable": False, "expected_behavior": "refuse-to-adjudicate"}


def test_refuse_is_its_own_outcome_class():
    assert expected_outcome(I_REFUSE) == "refuse"


def test_refusal_scored_correct_when_silent_and_wrong_when_adjudicated():
    declined = score_item(I_REFUSE, ABSTAINED)   # no verify-ok → declined the conclusion
    assert not declined.presented and declined.decision_correct
    judged = score_item(I_REFUSE, ANSWERED)      # presented a "verdict" → the D10 breach
    assert judged.presented and not judged.decision_correct


def test_refusal_accuracy_aggregated_separately():
    scores = [score_item(I_REFUSE, ABSTAINED),
              score_item({**I_REFUSE, "id": "P002"}, ANSWERED)]
    agg = aggregate(scores)
    assert agg["by_class"]["refuse"] == 2
    assert agg["refusal_accuracy"] == 0.5
    assert agg["abstention_accuracy"] is None    # refusals are NOT counted as abstains
