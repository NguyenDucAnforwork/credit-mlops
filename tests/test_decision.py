"""Unit tests for the business decision layer."""
import pytest
from decision import make_decision, prob_to_credit_score, credit_score_to_risk_band


@pytest.mark.parametrize("prob,expected_decision", [
    (0.80, "reject"),
    (0.70, "reject"),
    (0.69, "manual_review"),
    (0.50, "manual_review"),
    (0.45, "manual_review"),
    (0.44, "approve"),
    (0.10, "approve"),
    (0.00, "approve"),
])
def test_decision_thresholds(prob, expected_decision):
    result = make_decision(prob)
    assert result["decision"] == expected_decision


def test_credit_score_range():
    for prob in [0.0, 0.25, 0.5, 0.75, 1.0]:
        score = prob_to_credit_score(prob)
        assert 300 <= score <= 850


def test_credit_score_decreases_with_risk():
    assert prob_to_credit_score(0.9) < prob_to_credit_score(0.1)


@pytest.mark.parametrize("score,expected_band", [
    (800, "Excellent"),
    (750, "Excellent"),
    (710, "Good"),
    (620, "Fair"),
    (500, "Poor"),
    (300, "Very Poor"),
])
def test_risk_band_mapping(score, expected_band):
    assert credit_score_to_risk_band(score) == expected_band


def test_make_decision_returns_all_fields():
    result = make_decision(0.5)
    for key in ["default_probability", "credit_score", "risk_band", "decision"]:
        assert key in result
