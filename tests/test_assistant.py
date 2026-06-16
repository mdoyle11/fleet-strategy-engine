import pandas as pd
import pytest

from fleet_strategy_engine.assistant import (
    AssistantValidationError,
    build_assistant_context,
    deterministic_fallback,
    parse_validation_result,
    route_after_validation,
)


def recommendation_row(**overrides):
    row = {
        "station": "JFK",
        "region": "Northeast",
        "segment": "SUV",
        "fleet_size": 50,
        "utilization_pct": 92.0,
        "daily_margin": 65.0,
        "daily_roi": 1.1818,
        "price_gap_pct": -4.0,
        "market_share_pct": 16.0,
        "recommendation": "BUY",
        "recommendation_score": 0.83,
        "confidence": "high",
        "recommended_fleet_delta": 4,
        "pricing_signal": "near_competitor_price",
        "reason_codes": "utilization_above_90|strong_margin",
        "reasoning": "BUY because utilization and ROI are strong.",
    }
    row.update(overrides)
    return row


def test_build_assistant_context_uses_filtered_recommendations() -> None:
    df = pd.DataFrame(
        [
            recommendation_row(),
            recommendation_row(
                station="ORD",
                region="Midwest",
                segment="Economy",
                recommendation="REDUCE",
                recommendation_score=-0.67,
                recommended_fleet_delta=-3,
            ),
        ]
    )

    context = build_assistant_context(df)

    assert context["filtered_summary"]["visible_rows"] == 2
    assert context["filtered_summary"]["recommendation_counts"] == {
        "BUY": 1,
        "HOLD": 0,
        "REDUCE": 1,
    }
    assert context["filtered_summary"]["net_recommended_fleet_delta"] == 1
    assert context["recommendation_rows"][0]["station"] == "JFK"
    assert "reason_codes" in context["reason_code_reference"]


def test_parse_validation_result_requires_boolean_valid_flag() -> None:
    assert parse_validation_result('{"valid": true, "issue": ""}') == {
        "valid": True,
        "issue": "",
    }

    with pytest.raises(AssistantValidationError):
        parse_validation_result('{"valid": "yes", "issue": ""}')

    with pytest.raises(AssistantValidationError):
        parse_validation_result("not json")


def test_validation_router_retries_then_falls_back() -> None:
    assert route_after_validation(
        {
            "validation": {"valid": True, "issue": ""},
            "repair_attempts": 0,
        }
    ) == "finalize"
    assert route_after_validation(
        {
            "validation": {"valid": False, "issue": "unsupported claim"},
            "repair_attempts": 0,
        }
    ) == "repair_answer"
    assert route_after_validation(
        {
            "validation": {"valid": False, "issue": "unsupported claim"},
            "repair_attempts": 2,
        }
    ) == "fallback"


def test_deterministic_fallback_uses_recommendation_output() -> None:
    df = pd.DataFrame(
        [
            recommendation_row(),
            recommendation_row(
                station="ORD",
                region="Midwest",
                segment="Economy",
                recommendation="REDUCE",
                recommendation_score=-0.67,
                recommended_fleet_delta=-3,
            ),
        ]
    )
    context = build_assistant_context(df)

    fallback = deterministic_fallback(
        context,
        "answer changed the recommendation",
    )

    assert "deterministic summary" in fallback
    assert "BUY / HOLD / REDUCE counts: 1 / 0 / 1" in fallback
    assert "JFK / SUV: BUY" in fallback
    assert "ORD / Economy: REDUCE" in fallback
