import pandas as pd

from fleet_strategy_engine.engine.recommend import add_recommendations
from fleet_strategy_engine.pipeline.features import add_features


def score_input(**overrides):
    row = {
        "station": "JFK",
        "segment": "SUV",
        "fleet_size": 50,
        "utilization_pct": 84,
        "avg_daily_rate": 120,
        "avg_daily_fleet_cost": 40,
        "avg_daily_operating_cost": 15,
        "competitor_rate": 125,
        "market_share_pct": 12,
    }
    row.update(overrides)
    df = add_features(pd.DataFrame([row]))
    return add_recommendations(df).iloc[0]


def test_high_utilization_positive_margin_recommends_buy() -> None:
    row = score_input(utilization_pct=94, market_share_pct=16)

    assert row["recommendation"] == "BUY"
    assert row["recommended_fleet_delta"] > 0


def test_low_utilization_weak_share_recommends_reduce() -> None:
    row = score_input(utilization_pct=68, market_share_pct=7)

    assert row["recommendation"] == "REDUCE"
    assert row["recommended_fleet_delta"] < 0


def test_target_range_balanced_signals_recommends_hold() -> None:
    row = score_input(utilization_pct=84, market_share_pct=12)

    assert row["recommendation"] == "HOLD"
    assert row["recommended_fleet_delta"] == 0


def test_non_positive_margin_blocks_buy() -> None:
    row = score_input(
        utilization_pct=95,
        avg_daily_rate=50,
        avg_daily_fleet_cost=40,
        avg_daily_operating_cost=15,
        market_share_pct=16,
    )

    assert row["recommendation"] != "BUY"
    assert "non_positive_margin" in row["reason_codes"]


def test_discounted_high_utilization_is_cautious_buy_signal() -> None:
    row = score_input(utilization_pct=94, avg_daily_rate=100, competitor_rate=125, market_share_pct=16)

    assert row["recommendation"] == "BUY"
    assert row["confidence"] in {"medium", "high"}
    assert "discounted_vs_competitor_with_high_utilization" in row["reason_codes"]

