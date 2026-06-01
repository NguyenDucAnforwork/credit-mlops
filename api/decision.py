"""
Business rule / decision layer — completely separate from the model.
Maps raw default probability → credit_score, risk_band, decision.
"""
from __future__ import annotations


def prob_to_credit_score(prob: float) -> int:
    """Linear mapping: prob 0→850, prob 1→300 (higher score = lower risk)."""
    return int(round(850 - prob * 550))


def credit_score_to_risk_band(score: int) -> str:
    if score >= 750:
        return "Excellent"
    elif score >= 670:
        return "Good"
    elif score >= 580:
        return "Fair"
    elif score >= 440:
        return "Poor"
    return "Very Poor"


def make_decision(default_prob: float) -> dict:
    """
    Decision thresholds calibrated for credit bureau scoring.
    70%+ default probability → reject (too risky for any product)
    45-70% → manual_review (need human underwriter)
    <45%   → approve
    """
    if default_prob >= 0.70:
        decision = "reject"
    elif default_prob >= 0.45:
        decision = "manual_review"
    else:
        decision = "approve"

    score = prob_to_credit_score(default_prob)
    risk_band = credit_score_to_risk_band(score)

    return {
        "default_probability": round(default_prob, 4),
        "credit_score": score,
        "risk_band": risk_band,
        "decision": decision,
    }
