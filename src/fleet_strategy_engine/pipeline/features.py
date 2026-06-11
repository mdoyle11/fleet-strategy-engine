import math

import pandas as pd

from fleet_strategy_engine.config import DEFAULT_CONFIG, EngineConfig


def add_features(df: pd.DataFrame, config: EngineConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    featured = df.copy()

    numeric_columns = [
        "fleet_size",
        "utilization_pct",
        "avg_daily_rate",
        "avg_daily_fleet_cost",
        "avg_daily_operating_cost",
        "competitor_rate",
        "market_share_pct",
    ]
    for column in numeric_columns:
        featured[column] = pd.to_numeric(featured[column])

    featured["daily_margin"] = (
        featured["avg_daily_rate"]
        - featured["avg_daily_fleet_cost"]
        - featured["avg_daily_operating_cost"]
    )
    featured["price_gap"] = featured["avg_daily_rate"] - featured["competitor_rate"]
    featured["price_gap_pct"] = featured["price_gap"] / featured["competitor_rate"] * 100
    featured["estimated_rented_cars"] = (
        featured["fleet_size"] * featured["utilization_pct"] / 100
    )
    featured["target_fleet_at_85_util"] = featured["estimated_rented_cars"].apply(
        lambda value: int(math.ceil(value / config.target_utilization))
    )
    featured["utilization_band"] = featured["utilization_pct"].apply(utilization_band)
    featured["margin_band"] = featured["daily_margin"].apply(margin_band)
    featured["pricing_signal"] = featured.apply(
        lambda row: pricing_signal(row["price_gap_pct"], row["utilization_pct"]),
        axis=1,
    )
    featured["market_share_signal"] = featured["market_share_pct"].apply(
        lambda value: market_share_signal(value, config)
    )
    return featured


def utilization_band(utilization_pct: float) -> str:
    if utilization_pct < 70:
        return "severely_underutilized"
    if utilization_pct < 75:
        return "underutilized"
    if utilization_pct < 80:
        return "slightly_under_target"
    if utilization_pct <= 88:
        return "target_range"
    if utilization_pct < 90:
        return "slightly_above_target"
    return "capacity_constrained"


def margin_band(daily_margin: float) -> str:
    if daily_margin <= 0:
        return "negative_or_zero_margin"
    if daily_margin < 15:
        return "thin_margin"
    if daily_margin < 40:
        return "healthy_margin"
    return "strong_margin"


def pricing_signal(price_gap_pct: float, utilization_pct: float) -> str:
    if price_gap_pct <= -10 and utilization_pct >= 90:
        return "high_utilization_but_discounted_vs_competitor"
    if price_gap_pct <= -10:
        return "discounted_vs_competitor"
    if price_gap_pct >= 10 and utilization_pct >= 90:
        return "premium_price_and_still_capacity_constrained"
    if price_gap_pct >= 10 and utilization_pct < 80:
        return "premium_price_with_weak_utilization"
    return "near_competitor_price"


def market_share_signal(market_share_pct: float, config: EngineConfig = DEFAULT_CONFIG) -> str:
    if market_share_pct >= config.strong_market_share_pct:
        return "strong_share"
    if market_share_pct < config.weak_market_share_pct:
        return "weak_share"
    return "moderate_share"

