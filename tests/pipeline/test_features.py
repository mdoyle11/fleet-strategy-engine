import pandas as pd

from fleet_strategy_engine.pipeline.features import (
    add_features,
    margin_band,
    market_share_signal,
    pricing_signal,
    utilization_band,
)


def test_add_features_calculates_expected_metrics() -> None:
    df = pd.DataFrame(
        [
            {
                "station": "AAA",
                "segment": "SUV",
                "fleet_size": 50,
                "utilization_pct": 85,
                "avg_daily_rate": 120,
                "avg_daily_fleet_cost": 35,
                "avg_daily_operating_cost": 15,
                "competitor_rate": 100,
                "market_share_pct": 16,
            }
        ]
    )

    result = add_features(df)

    assert result.loc[0, "daily_margin"] == 70
    assert result.loc[0, "price_gap"] == 20
    assert result.loc[0, "price_gap_pct"] == 20
    assert result.loc[0, "estimated_rented_cars"] == 42.5
    assert result.loc[0, "target_fleet_at_85_util"] == 50


def test_band_and_signal_helpers() -> None:
    assert utilization_band(68) == "severely_underutilized"
    assert utilization_band(84) == "target_range"
    assert utilization_band(93) == "capacity_constrained"
    assert margin_band(-1) == "negative_or_zero_margin"
    assert margin_band(25) == "healthy_margin"
    assert pricing_signal(-12, 92) == "high_utilization_but_discounted_vs_competitor"
    assert pricing_signal(12, 75) == "premium_price_with_weak_utilization"
    assert market_share_signal(16) == "strong_share"
    assert market_share_signal(8) == "weak_share"

