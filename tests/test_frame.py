"""Standing tests for question-frame constraint coverage (ROADMAP M2-T8, D13)."""

from attest.frame import Constraint, CoverageResult, QuestionFrame, check_coverage


def _frame(*pairs):
    return QuestionFrame("q", [Constraint(role, text) for role, text in pairs])


def test_complete_when_all_constraints_present():
    frame = _frame(("metric", "Total assets"), ("period", "September 28, 2024"))
    cited = ["Total assets $ 364,980 $ 352,583", "For the fiscal year ended September 28, 2024"]
    result = check_coverage(frame, cited)
    assert result.complete
    assert not result.missing


def test_incomplete_when_a_constraint_is_missing():
    """The crux: the answer token is present but the question's subject is not."""
    frame = _frame(("metric", "Total assets"))
    # A real span containing 364,980 — but it's the liabilities+equity total, not assets.
    cited = ["Total liabilities and shareholders' equity $ 364,980 $ 352,583"]
    result = check_coverage(frame, cited)
    assert not result.complete
    assert [c.role for c in result.missing] == ["metric"]


def test_missing_period_is_caught():
    frame = _frame(("metric", "Total assets"), ("period", "September 28, 2024"))
    cited = ["Total assets $ 364,980 $ 352,583"]  # figure + metric, but no period span
    result = check_coverage(frame, cited)
    assert not result.complete
    assert [c.role for c in result.missing] == ["period"]


def test_coverage_is_case_and_whitespace_insensitive():
    frame = _frame(("subject", "wheel well"))
    assert check_coverage(frame, ["The  WHEEL   WELL is red."]).complete


def test_optional_constraint_absent_is_satisfied():
    frame = QuestionFrame("q", [Constraint("entity", "Apple", required=False)])
    assert check_coverage(frame, ["Total assets $ 364,980 $ 352,583"]).complete


def test_connecting_clause_demonstrates_relation():
    """A span carrying both subject and attribute covers the question; the bare answer doesn't."""
    frame = _frame(("subject", "wheel well"), ("attribute", "color"))
    bare = check_coverage(frame, ["red"])                       # answer token alone
    clause = check_coverage(frame, ["the wheel well color is red"])
    assert not bare.complete and clause.complete
    assert isinstance(clause, CoverageResult)
