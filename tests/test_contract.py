"""
Schema contract tests — verify the API's Pydantic models enforce
the right shapes, types, and constraints.
"""
import pytest
from pydantic import ValidationError
from schemas import PredictRequest, PredictResponse, HealthResponse


class TestPredictRequest:
    def test_all_optional_fields(self):
        req = PredictRequest()
        assert req.NUMBER_OF_LOANS is None

    def test_partial_payload_accepted(self):
        req = PredictRequest(NUMBER_OF_LOANS=5, ENQUIRIES_3M=3)
        assert req.NUMBER_OF_LOANS == 5

    def test_extra_fields_allowed(self):
        req = PredictRequest(UNKNOWN_FIELD=99)
        assert req.UNKNOWN_FIELD == 99


class TestPredictResponse:
    def test_valid_response_constructs(self):
        r = PredictResponse(
            default_probability=0.5,
            credit_score=600,
            risk_band="Fair",
            decision="manual_review",
            model_version="v1",
            latency_ms=12.3,
        )
        assert r.decision == "manual_review"

    def test_invalid_probability_rejected(self):
        with pytest.raises(ValidationError):
            PredictResponse(
                default_probability=1.5,
                credit_score=600,
                risk_band="Fair",
                decision="approve",
                model_version="v1",
                latency_ms=10.0,
            )

    def test_invalid_decision_rejected(self):
        with pytest.raises(ValidationError):
            PredictResponse(
                default_probability=0.5,
                credit_score=600,
                risk_band="Fair",
                decision="maybe",
                model_version="v1",
                latency_ms=10.0,
            )

    def test_invalid_risk_band_rejected(self):
        with pytest.raises(ValidationError):
            PredictResponse(
                default_probability=0.5,
                credit_score=600,
                risk_band="Unknown",
                decision="approve",
                model_version="v1",
                latency_ms=10.0,
            )

    def test_credit_score_bounds(self):
        with pytest.raises(ValidationError):
            PredictResponse(
                default_probability=0.5,
                credit_score=200,  # below 300
                risk_band="Very Poor",
                decision="reject",
                model_version="v1",
                latency_ms=10.0,
            )


class TestHealthResponse:
    def test_valid_health(self):
        h = HealthResponse(status="ok", model_version="v1", uptime_s=100.0)
        assert h.status == "ok"

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            HealthResponse(status="unknown", model_version="v1", uptime_s=0)
