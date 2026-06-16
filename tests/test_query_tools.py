import pandas as pd
import pytest

from fleet_strategy_engine.assistant.query_tools import (
    QueryToolError,
    lookup_opportunity,
    planning_context,
    query_opportunities,
)


def recommendations() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "station": "ATL",
                "region": "South",
                "segment": "SUV",
                "fleet_size": 50,
                "utilization_pct": 92.0,
                "daily_margin": 65.0,
                "daily_roi": 1.1818,
                "estimated_daily_profit": 2830.0,
                "price_gap_pct": -4.0,
                "market_share_pct": 16.0,
                "recommendation": "BUY",
                "recommendation_score": 0.83,
                "confidence": "high",
                "recommended_fleet_delta": 4,
                "pricing_signal": "near_competitor_price",
                "reason_codes": "utilization_above_90|strong_margin",
                "reasoning": "BUY because utilization and ROI are strong.",
            },
            {
                "station": "ORD",
                "region": "Midwest",
                "segment": "Economy",
                "fleet_size": 80,
                "utilization_pct": 68.0,
                "daily_margin": 8.0,
                "daily_roi": 0.2162,
                "estimated_daily_profit": -240.0,
                "price_gap_pct": -10.0,
                "market_share_pct": 7.0,
                "recommendation": "REDUCE",
                "recommendation_score": -0.67,
                "confidence": "high",
                "recommended_fleet_delta": -3,
                "pricing_signal": "discounted_vs_competitor",
                "reason_codes": "utilization_below_70|weak_market_share",
                "reasoning": "REDUCE because utilization and share are weak.",
            },
            {
                "station": "LAX",
                "region": "West",
                "segment": "SUV",
                "fleet_size": 40,
                "utilization_pct": 89.0,
                "daily_margin": 45.0,
                "daily_roi": 0.75,
                "estimated_daily_profit": 1602.0,
                "price_gap_pct": 6.0,
                "market_share_pct": 14.0,
                "recommendation": "BUY",
                "recommendation_score": 0.5,
                "confidence": "medium",
                "recommended_fleet_delta": 2,
                "pricing_signal": "near_competitor_price",
                "reason_codes": "utilization_near_upper_target|strong_margin",
                "reasoning": "BUY because utilization is near the upper target.",
            },
        ]
    )


def test_lookup_opportunity_returns_exact_station_segment() -> None:
    result = lookup_opportunity(recommendations(), "atl", "suv")

    assert result["matched_row_count"] == 1
    assert result["rows"][0]["station"] == "ATL"
    assert result["rows"][0]["segment"] == "SUV"


def test_query_opportunities_filters_and_sorts() -> None:
    result = query_opportunities(
        recommendations(),
        filters={"segment": "SUV", "recommendation": "BUY"},
        sort_by="recommendation_score",
        sort_direction="asc",
        limit=1,
    )

    assert result["matched_row_count"] == 2
    assert result["returned_row_count"] == 1
    assert result["rows"][0]["station"] == "LAX"


def test_query_opportunities_supports_station_segment_comparison() -> None:
    result = query_opportunities(
        recommendations(),
        filters={"station": "ATL", "segment": ["Economy", "SUV"]},
        sort_by="segment",
        sort_direction="asc",
    )

    assert result["matched_row_count"] == 1
    assert result["rows"][0]["station"] == "ATL"
    assert result["rows"][0]["segment"] == "SUV"


def test_query_opportunities_supports_numeric_ranges() -> None:
    result = query_opportunities(
        recommendations(),
        filters={"utilization_pct": {"min": 90}},
    )

    assert result["matched_row_count"] == 1
    assert result["rows"][0]["station"] == "ATL"


def test_query_opportunities_rejects_unknown_filters() -> None:
    with pytest.raises(QueryToolError, match="Unsupported query filters"):
        query_opportunities(recommendations(), filters={"unknown": "value"})


def test_planning_context_exposes_available_values() -> None:
    context = planning_context(recommendations())

    assert "West" in context["available_values"]["region"]
    assert "SUV" in context["available_values"]["segment"]
    assert "query_opportunities" in context["available_tools"]
