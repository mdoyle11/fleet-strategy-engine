import pandas as pd

from fleet_strategy_engine.engine.pricing import pricing_guidance
from fleet_strategy_engine.pipeline.features import add_features


def make_row(**overrides):
    row = {
        "station": "JFK",
        "segment": "SUV",
        "fleet_size": 50,
        "utilization_pct": 92,
        "avg_daily_rate": 100,
        "avg_daily_fleet_cost": 40,
        "avg_daily_operating_cost": 15,
        "competitor_rate": 125,
        "market_share_pct": 16,
        "recommendation": "BUY",
    }
    row.update(overrides)
    return add_features(pd.DataFrame([row])).iloc[0]


def test_high_utilization_discounted_positive_margin_recommends_price_test() -> None:
    result = pricing_guidance(make_row())

    assert result["pricing_action"] == "RAISE_PRICE_TEST"
    assert "price_below_competitor_high_utilization_positive_margin" in result["pricing_reason_codes"]
    assert "strong_share_supports_pricing_power" in result["pricing_reason_codes"]


def test_high_utilization_above_competitor_supports_holding_price() -> None:
    result = pricing_guidance(make_row(avg_daily_rate=132, competitor_rate=125))

    assert result["pricing_action"] == "HOLD_PRICE"
    assert "priced_above_competitor_and_still_high_utilization" in result["pricing_reason_codes"]


def test_weak_utilization_above_competitor_recommends_price_review() -> None:
    result = pricing_guidance(
        make_row(
            utilization_pct=72,
            avg_daily_rate=140,
            competitor_rate=125,
            market_share_pct=8,
            recommendation="REDUCE",
        )
    )

    assert result["pricing_action"] == "PRICE_COMPETITIVENESS_REVIEW"
    assert "priced_above_competitor_with_weak_utilization" in result["pricing_reason_codes"]
    assert "weak_share_limits_pricing_power" in result["pricing_reason_codes"]

