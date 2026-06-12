from typing import Any

import pandas as pd

from fleet_strategy_engine.config import DEFAULT_CONFIG, EngineConfig


PRICING_ACTIONS = [
    "RAISE_PRICE_TEST",
    "HOLD_PRICE",
    "PRICE_COMPETITIVENESS_REVIEW",
    "MONITOR_PRICE",
]


def add_pricing_guidance(
    df: pd.DataFrame,
    config: EngineConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    guided = df.copy()
    guidance = guided.apply(lambda row: pricing_guidance(row, config), axis=1)
    guidance_df = pd.DataFrame(guidance.tolist(), index=guided.index)
    for column in guidance_df.columns:
        guided[column] = guidance_df[column]
    return guided


def pricing_guidance(row: pd.Series, config: EngineConfig = DEFAULT_CONFIG) -> dict[str, Any]:
    util = float(row["utilization_pct"])
    margin = float(row["daily_margin"])
    share = float(row["market_share_pct"])
    price_gap_pct = float(row["price_gap_pct"])
    recommendation = row.get("recommendation")

    reason_codes: list[str] = []

    if util >= config.high_utilization_pct and price_gap_pct <= -10 and margin > 0:
        action = "RAISE_PRICE_TEST"
        reason_codes.append("price_below_competitor_high_utilization_positive_margin")
        if share >= config.strong_market_share_pct:
            reason_codes.append("strong_share_supports_pricing_power")
    elif util >= config.high_utilization_pct and price_gap_pct >= 5 and margin > 0:
        action = "HOLD_PRICE"
        reason_codes.append("priced_above_competitor_and_still_high_utilization")
        if recommendation == "BUY":
            reason_codes.append("pricing_power_supports_buy_case")
    elif util < 80 and price_gap_pct >= 10:
        action = "PRICE_COMPETITIVENESS_REVIEW"
        reason_codes.append("priced_above_competitor_with_weak_utilization")
    elif margin <= 0:
        action = "PRICE_COMPETITIVENESS_REVIEW"
        reason_codes.append("non_positive_margin_requires_price_or_cost_review")
    else:
        action = "MONITOR_PRICE"
        reason_codes.append("pricing_signal_balanced")

    if util < config.underutilized_pct and price_gap_pct <= -10:
        reason_codes.append("discounting_not_solving_low_utilization")
    if share < config.weak_market_share_pct:
        reason_codes.append("weak_share_limits_pricing_power")

    return {
        "pricing_action": action,
        "pricing_reason_codes": reason_codes,
    }

