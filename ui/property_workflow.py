from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CreditDecision = Literal["approve", "manual_review", "reject"]


@dataclass(frozen=True)
class PropertyScenario:
    name: str
    description: str
    province: str
    district: str
    property_type: str
    area_m2: float
    published_at: str
    loan_amount_vnd: float
    credit_decision: CreditDecision
    map_latitude: float
    map_longitude: float


PROPERTY_SCENARIOS: tuple[PropertyScenario, ...] = (
    PropertyScenario(
        name="Ha Noi apartment",
        description="Urban apartment with mainstream comparable support.",
        province="Hà Nội",
        district="Cầu Giấy",
        property_type="apartment",
        area_m2=55.0,
        published_at="2025-12-15T00:00:00Z",
        loan_amount_vnd=1_500_000_000.0,
        credit_decision="approve",
        map_latitude=21.0362,
        map_longitude=105.7906,
    ),
    PropertyScenario(
        name="Ho Chi Minh City house",
        description="Central-city house with larger ticket size.",
        province="Hồ Chí Minh",
        district="1",
        property_type="house",
        area_m2=60.0,
        published_at="2025-12-15T00:00:00Z",
        loan_amount_vnd=4_000_000_000.0,
        credit_decision="approve",
        map_latitude=10.7756,
        map_longitude=106.7009,
    ),
    PropertyScenario(
        name="Low-support manual review",
        description="Rare district/type combination used to exercise low-support review handling.",
        province="Hà Nội",
        district="Không rõ",
        property_type="villa",
        area_m2=450.0,
        published_at="2025-12-15T00:00:00Z",
        loan_amount_vnd=30_000_000_000.0,
        credit_decision="manual_review",
        map_latitude=21.0278,
        map_longitude=105.8342,
    ),
)


def scenario_by_name(name: str) -> PropertyScenario:
    for scenario in PROPERTY_SCENARIOS:
        if scenario.name == name:
            return scenario
    raise ValueError(f"Unknown property scenario: {name}")


def property_payload(
    *,
    published_at: str,
    province: str,
    district: str,
    property_type: str,
    area_m2: float,
) -> dict:
    return {
        "published_at": published_at,
        "province": province,
        "district": district,
        "property_type": property_type,
        "area_m2": float(area_m2),
    }


def lending_payload(
    *,
    credit_decision: CreditDecision,
    loan_amount_vnd: float,
    lower_value_vnd: float,
    confidence: str,
    ood: bool = False,
) -> dict:
    return {
        "credit_decision": credit_decision,
        "loan_amount_vnd": float(loan_amount_vnd),
        "lower_value_vnd": float(lower_value_vnd),
        "confidence": confidence,
        "ood": bool(ood),
    }


def conservative_ltv(loan_amount_vnd: float, lower_value_vnd: float) -> float:
    if lower_value_vnd <= 0:
        return float("inf")
    return float(loan_amount_vnd / lower_value_vnd)
