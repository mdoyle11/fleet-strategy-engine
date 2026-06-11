import pandas as pd

from fleet_strategy_engine.engine.recommend import add_recommendations, score_row
from fleet_strategy_engine.pipeline.features import add_features


def make_featured_row(**overrides):
    row = {
        "station": "AAA",
        "segment": "SUV",
        "fleet_size": 50,
        "utilization_pct": 92,
        "avg_daily_rate": 120,
        "avg_daily_fleet_cost": 35,
        "avg_daily_operating_cost": 15,
        "competitor_rate": 125,
        "market_share_pct": 16,
    }
    row.update(overrides)
    return add_features(pd.DataFrame([row])).iloc[0]


def test_high_utilization_positive_margin_recommends_buy() -> None:
    result = score_row(make_featured_row())

    assert result["recommendation"] == "BUY"
    assert "utilization_above_90" in result["reason_codes"]


def test_low_utilization_weak_share_recommends_reduce() -> None:
    result = score_row(make_featured_row(utilization_pct=68, market_share_pct=7))

    assert result["recommendation"] == "REDUCE"


def test_target_range_recommends_hold() -> None:
    result = score_row(make_featured_row(utilization_pct=84, market_share_pct=12))

    assert result["recommendation"] == "HOLD"


def test_non_positive_margin_blocks_buy() -> None:
    result = score_row(
        make_featured_row(
            utilization_pct=95,
            avg_daily_rate=40,
            avg_daily_fleet_cost=35,
            avg_daily_operating_cost=15,
        )
    )

    assert result["recommendation"] != "BUY"
    assert "non_positive_margin" in result["reason_codes"]


def test_fleet_delta_is_capped() -> None:
    df = add_features(
        pd.DataFrame(
            [
                {
                    "station": "AAA",
                    "segment": "SUV",
                    "fleet_size": 50,
                    "utilization_pct": 96,
                    "avg_daily_rate": 120,
                    "avg_daily_fleet_cost": 35,
                    "avg_daily_operating_cost": 15,
                    "competitor_rate": 125,
                    "market_share_pct": 16,
                }
            ]
        )
    )

    result = add_recommendations(df)

    assert result.loc[0, "recommendation"] == "BUY"
    assert result.loc[0, "recommended_fleet_delta"] <= 10

