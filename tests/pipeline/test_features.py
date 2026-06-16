import pandas as pd

from fleet_strategy_engine.pipeline.features import (
    add_features,
    daily_roi,
    market_share_signal,
    pricing_signal,
    roi_band,
    station_region,
    utilization_band,
)


def test_add_features_calculates_core_metrics() -> None:
    df = pd.DataFrame(
        [
            {
                "station": "JFK",
                "segment": "SUV",
                "fleet_size": 50,
                "utilization_pct": 92,
                "avg_daily_rate": 120,
                "avg_daily_fleet_cost": 40,
                "avg_daily_operating_cost": 15,
                "competitor_rate": 125,
                "market_share_pct": 16,
            }
        ]
    )

    result = add_features(df)

    assert result.loc[0, "daily_margin"] == 65
    assert result.loc[0, "daily_cost"] == 55
    assert round(result.loc[0, "daily_roi"], 4) == 1.1818
    assert result.loc[0, "price_gap"] == -5
    assert result.loc[0, "price_gap_pct"] == -4
    assert result.loc[0, "estimated_rented_cars"] == 46
    assert result.loc[0, "target_fleet_at_85_util"] == 55
    assert result.loc[0, "region"] == "Northeast"


def test_station_region_maps_airport_codes_to_main_us_regions() -> None:
    assert station_region("JFK") == "Northeast"
    assert station_region("ATL") == "South"
    assert station_region("ORD") == "Midwest"
    assert station_region("LAX") == "West"
    assert station_region("missing") == "Unknown"


def test_band_helpers() -> None:
    assert utilization_band(69) == "severely_underutilized"
    assert utilization_band(74) == "underutilized"
    assert utilization_band(84) == "target_range"
    assert utilization_band(91) == "capacity_constrained"

    assert daily_roi(65, 55) == 65 / 55
    assert daily_roi(65, 0) == 0
    assert roi_band(-0.1) == "negative_or_zero_roi"
    assert roi_band(0.1) == "thin_roi"
    assert roi_band(0.5) == "healthy_roi"
    assert roi_band(0.8) == "strong_roi"


def test_signal_helpers() -> None:
    assert pricing_signal(-12, 92) == "high_utilization_but_discounted_vs_competitor"
    assert pricing_signal(-12, 80) == "discounted_vs_competitor"
    assert pricing_signal(12, 92) == "premium_price_and_still_capacity_constrained"
    assert pricing_signal(0, 84) == "near_competitor_price"

    assert market_share_signal(8) == "weak_share"
    assert market_share_signal(12) == "moderate_share"
    assert market_share_signal(16) == "strong_share"
