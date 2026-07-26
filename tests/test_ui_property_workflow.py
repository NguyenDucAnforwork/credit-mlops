from __future__ import annotations

from ui.property_workflow import (
    PROPERTY_SCENARIOS,
    conservative_ltv,
    lending_payload,
    property_payload,
    scenario_by_name,
)


def test_required_property_scenarios_are_present():
    names = {scenario.name for scenario in PROPERTY_SCENARIOS}

    assert "Ha Noi apartment" in names
    assert "Ho Chi Minh City house" in names
    assert "Low-support manual review" in names


def test_property_payload_matches_avm_contract():
    payload = property_payload(
        published_at="2025-12-15T00:00:00Z",
        province="Hà Nội",
        district="Cầu Giấy",
        property_type="apartment",
        area_m2=55,
    )

    assert payload == {
        "published_at": "2025-12-15T00:00:00Z",
        "province": "Hà Nội",
        "district": "Cầu Giấy",
        "property_type": "apartment",
        "area_m2": 55.0,
    }


def test_lending_payload_uses_lower_interval_for_conservative_ltv():
    payload = lending_payload(
        credit_decision="approve",
        loan_amount_vnd=750,
        lower_value_vnd=1000,
        confidence="high",
    )

    assert payload["lower_value_vnd"] == 1000.0
    assert conservative_ltv(payload["loan_amount_vnd"], payload["lower_value_vnd"]) == 0.75


def test_low_support_scenario_routes_to_manual_review_fixture():
    scenario = scenario_by_name("Low-support manual review")

    assert scenario.credit_decision == "manual_review"
    assert scenario.property_type == "villa"
    assert conservative_ltv(scenario.loan_amount_vnd, 0) == float("inf")
