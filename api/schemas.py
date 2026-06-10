from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    SHORT_TERM_COUNT: float | None = None
    MID_TERM_COUNT: float | None = None
    LONG_TERM_COUNT: float | None = None
    SHORT_TERM_COUNT_BANK: float | None = None
    MID_TERM_COUNT_BANK: float | None = None
    LONG_TERM_COUNT_BANK: float | None = None
    SHORT_TERM_COUNT_NON_BANK: float | None = None
    MID_TERM_COUNT_NON_BANK: float | None = None
    LONG_TERM_COUNT_NON_BANK: float | None = None
    NUMBER_OF_LOANS: float | None = None
    NUMBER_OF_LOANS_BANK: float | None = None
    NUMBER_OF_LOANS_NON_BANK: float | None = None
    NUMBER_OF_CREDIT_CARDS: float | None = None
    NUMBER_OF_CREDIT_CARDS_BANK: float | None = None
    NUMBER_OF_CREDIT_CARDS_NON_BANK: float | None = None
    NUMBER_OF_RELATIONSHIP: float | None = None
    NUMBER_OF_RELATIONSHIP_BANK: float | None = None
    NUMBER_OF_RELATIONSHIP_NON_BANK: float | None = None
    NUM_NEW_LOAN_TAKEN_3M: float | None = None
    NUM_NEW_LOAN_TAKEN_6M: float | None = None
    NUM_NEW_LOAN_TAKEN_9M: float | None = None
    NUM_NEW_LOAN_TAKEN_12M: float | None = None
    NUM_NEW_LOAN_TAKEN_BANK_3M: float | None = None
    NUM_NEW_LOAN_TAKEN_BANK_6M: float | None = None
    NUM_NEW_LOAN_TAKEN_BANK_9M: float | None = None
    NUM_NEW_LOAN_TAKEN_BANK_12M: float | None = None
    NUM_NEW_LOAN_TAKEN_NON_BANK_3M: float | None = None
    NUM_NEW_LOAN_TAKEN_NON_BANK_6M: float | None = None
    NUM_NEW_LOAN_TAKEN_NON_BANK_9M: float | None = None
    NUM_NEW_LOAN_TAKEN_NON_BANK_12M: float | None = None
    OUTSTANDING_BAL_LOAN_CURRENT: float | None = None
    OUTSTANDING_BAL_LOAN_3M: float | None = None
    OUTSTANDING_BAL_LOAN_6M: float | None = None
    OUTSTANDING_BAL_LOAN_9M: float | None = None
    OUTSTANDING_BAL_LOAN_12M: float | None = None
    OUTSTANDING_BAL_CC_3M: float | None = None
    OUTSTANDING_BAL_CC_6M: float | None = None
    OUTSTANDING_BAL_CC_9M: float | None = None
    OUTSTANDING_BAL_CC_12M: float | None = None
    OUTSTANDING_BAL_ALL_3M: float | None = None
    OUTSTANDING_BAL_ALL_6M: float | None = None
    OUTSTANDING_BAL_ALL_9M: float | None = None
    OUTSTANDING_BAL_ALL_12M: float | None = None
    OUTSTANDING_BAL_LOAN_3M_6M: float | None = None
    OUTSTANDING_BAL_LOAN_6M_9M: float | None = None
    OUTSTANDING_BAL_LOAN_9M_12M: float | None = None
    OUTSTANDING_BAL_LOAN_6M_12M: float | None = None
    OUTSTANDING_BAL_LOAN_3M_12M: float | None = None
    OUTSTANDING_BAL_CC_3M_6M: float | None = None
    OUTSTANDING_BAL_CC_6M_9M: float | None = None
    OUTSTANDING_BAL_CC_9M_12M: float | None = None
    OUTSTANDING_BAL_CC_6M_12M: float | None = None
    OUTSTANDING_BAL_CC_3M_12M: float | None = None
    OUTSTANDING_BAL_ALL_3M_6M: float | None = None
    OUTSTANDING_BAL_ALL_6M_9M: float | None = None
    OUTSTANDING_BAL_ALL_9M_12M: float | None = None
    OUTSTANDING_BAL_ALL_6M_12M: float | None = None
    OUTSTANDING_BAL_ALL_3M_12M: float | None = None
    INCREASING_BAL_3M_LOAN: float | None = None
    INCREASING_BAL_6M_LOAN: float | None = None
    INCREASING_BAL_3M_CC: float | None = None
    INCREASING_BAL_6M_CC: float | None = None
    INCREASING_BAL_3M_ALL: float | None = None
    INCREASING_BAL_6M_ALL: float | None = None
    OUTSTANDING_BAL_CC_CURRENT: float | None = None
    CREDIT_CARD_MONTH_SINCE_10DPD: float | None = None
    CREDIT_CARD_MONTH_SINCE_30DPD: float | None = None
    CREDIT_CARD_MONTH_SINCE_60DPD: float | None = None
    CREDIT_CARD_MONTH_SINCE_90DPD: float | None = None
    CREDIT_CARD_NUMBER_OF_LATE_PAYMENT: float | None = None
    ENQUIRIES_3M: float | None = None
    ENQUIRIES_6M: float | None = None
    ENQUIRIES_9M: float | None = None
    ENQUIRIES_12M: float | None = None
    ENQUIRIES_FROM_BANK_3M: float | None = None
    ENQUIRIES_FROM_NON_BANK_3M: float | None = None
    ENQUIRIES_FOR_LOAN_3M: float | None = None
    ENQUIRIES_FOR_CC_3M: float | None = None
    ENQUIRIES_FROM_BANK_FOR_LOAN_3M: float | None = None
    ENQUIRIES_FROM_NON_BANK_FOR_LOAN_3M: float | None = None
    ENQUIRIES_FROM_BANK_FOR_CC_3M: float | None = None
    ENQUIRIES_FROM_NON_BANK_FOR_CC_3M: float | None = None
    ENQUIRIES_FROM_BANK_6M: float | None = None
    ENQUIRIES_FROM_NON_BANK_6M: float | None = None
    ENQUIRIES_FOR_LOAN_6M: float | None = None
    ENQUIRIES_FOR_CC_6M: float | None = None
    ENQUIRIES_FROM_BANK_FOR_LOAN_6M: float | None = None
    ENQUIRIES_FROM_NON_BANK_FOR_LOAN_6M: float | None = None
    ENQUIRIES_FROM_BANK_FOR_CC_6M: float | None = None
    ENQUIRIES_FROM_NON_BANK_FOR_CC_6M: float | None = None
    ENQUIRIES_FROM_BANK_9M: float | None = None
    ENQUIRIES_FROM_NON_BANK_9M: float | None = None
    ENQUIRIES_FOR_LOAN_9M: float | None = None
    ENQUIRIES_FOR_CC_9M: float | None = None
    ENQUIRIES_FROM_BANK_FOR_LOAN_9M: float | None = None
    ENQUIRIES_FROM_NON_BANK_FOR_LOAN_9M: float | None = None
    ENQUIRIES_FROM_BANK_FOR_CC_9M: float | None = None
    ENQUIRIES_FROM_NON_BANK_FOR_CC_9M: float | None = None
    ENQUIRIES_FROM_BANK_12M: float | None = None
    ENQUIRIES_FROM_NON_BANK_12M: float | None = None
    ENQUIRIES_FOR_LOAN_12M: float | None = None
    ENQUIRIES_FOR_CC_12M: float | None = None
    ENQUIRIES_FROM_BANK_FOR_LOAN_12M: float | None = None
    ENQUIRIES_FROM_NON_BANK_FOR_LOAN_12M: float | None = None
    ENQUIRIES_FROM_BANK_FOR_CC_12M: float | None = None
    ENQUIRIES_FROM_NON_BANK_FOR_CC_12M: float | None = None
    ENQUIRIES_3M_6M: float | None = None
    ENQUIRIES_6M_9M: float | None = None
    ENQUIRIES_9M_12M: float | None = None
    ENQUIRIES_6M_12M: float | None = None
    ENQUIRIES_3M_12M: float | None = None
    ENQUIRIES_FROM_BANK_3M_6M: float | None = None
    ENQUIRIES_FROM_BANK_6M_9M: float | None = None
    ENQUIRIES_FROM_BANK_9M_12M: float | None = None
    ENQUIRIES_FROM_BANK_6M_12M: float | None = None
    ENQUIRIES_FROM_BANK_3M_12M: float | None = None
    ENQUIRIES_FROM_NON_BANK_3M_6M: float | None = None
    ENQUIRIES_FROM_NON_BANK_6M_9M: float | None = None
    ENQUIRIES_FROM_NON_BANK_9M_12M: float | None = None
    ENQUIRIES_FROM_NON_BANK_6M_12M: float | None = None
    ENQUIRIES_FROM_NON_BANK_3M_12M: float | None = None
    OUTSTANDING_BAL_ALL_CURRENT: float | None = None

    model_config = {"extra": "allow"}


class PredictResponse(BaseModel):
    default_probability: float = Field(..., ge=0.0, le=1.0)
    credit_score: int = Field(..., ge=300, le=850)
    risk_band: Literal["Very Poor", "Poor", "Fair", "Good", "Excellent"]
    decision: Literal["approve", "manual_review", "reject"]
    model_version: str
    latency_ms: float
    scorecard_score: float | None = Field(
        None,
        description="Raw WOE-based credit score (scorecard model only)",
    )
    scorecard_breakdown: list[dict[str, Any]] | None = Field(
        None,
        description=(
            "Per-feature score breakdown when scorecard model is active. "
            "Each entry: {feature, raw_value, bin, woe, score_contribution, iv}. "
            "Sorted by |score_contribution| descending."
        ),
    )
    model_alias: str = Field(default="unknown", description="MLflow alias serving this request")
    trace_id: str = Field(default="", description="UUID4 per-request trace identifier")


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    model_version: str
    uptime_s: float
