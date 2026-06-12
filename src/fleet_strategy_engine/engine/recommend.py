from typing import Any

import pandas as pd

from fleet_strategy_engine.config import DEFAULT_CONFIG, EngineConfig
from fleet_strategy_engine.engine.pricing import add_pricing_guidance


def add_recommendations(df: pd.DataFrame, config: EngineConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    recommended = df.copy()
    scored = recommended.apply(lambda row: score_row(row, config), axis=1)
    scored_df = pd.DataFrame(scored.tolist(), index=recommended.index)
    for column in scored_df.columns:
        recommended[column] = scored_df[column]

    recommended["recommended_fleet_delta"] = recommended.apply(
        lambda row: recommended_fleet_delta(row, config),
        axis=1,
    )
    return add_pricing_guidance(recommended, config)


def score_row(row: pd.Series, config: EngineConfig = DEFAULT_CONFIG) -> dict[str, Any]:
    buy_score = 0
    reduce_score = 0
    reason_codes: list[str] = []

    util = float(row["utilization_pct"])
    margin = float(row["daily_margin"])
    share = float(row["market_share_pct"])
    price_gap_pct = float(row["price_gap_pct"])

    if util >= config.high_utilization_pct:
        buy_score += 3
        reason_codes.append("utilization_above_90")
    elif util >= 88:
        buy_score += 1
        reason_codes.append("utilization_near_upper_target")
    elif util < 70:
        reduce_score += 3
        reason_codes.append("utilization_below_70")
    elif util < config.underutilized_pct:
        reduce_score += 2
        reason_codes.append("utilization_below_75")
    elif 80 <= util <= 88:
        reason_codes.append("utilization_in_target_range")
    else:
        reason_codes.append("utilization_near_target")

    if margin <= 0:
        reduce_score += 2
        buy_score -= 4
        reason_codes.append("non_positive_margin")
    elif margin < 15:
        reduce_score += 1
        reason_codes.append("thin_margin")
    elif margin >= 40:
        buy_score += 1
        reason_codes.append("strong_margin")
    else:
        reason_codes.append("healthy_margin")

    if share >= config.strong_market_share_pct and util >= 88:
        buy_score += 2
        reason_codes.append("strong_share_and_high_utilization")
    elif share >= config.strong_market_share_pct:
        buy_score += 1
        reason_codes.append("strong_market_share")
    elif share < config.weak_market_share_pct and util < 80:
        reduce_score += 2
        reason_codes.append("weak_share_and_weak_utilization")
    elif share < config.weak_market_share_pct:
        reduce_score += 1
        reason_codes.append("weak_market_share")
    else:
        reason_codes.append("moderate_market_share")

    if price_gap_pct <= -10 and util >= config.high_utilization_pct:
        buy_score -= 1
        reason_codes.append("discounted_vs_competitor_with_high_utilization")
    elif price_gap_pct >= 5 and util >= config.high_utilization_pct:
        buy_score += 1
        reason_codes.append("above_competitor_and_still_high_utilization")
    elif price_gap_pct >= 10 and util < 80:
        reduce_score += 1
        reason_codes.append("above_competitor_with_weak_utilization")
    else:
        reason_codes.append("pricing_near_competitor")

    if buy_score >= 3 and buy_score > reduce_score and margin > 0:
        recommendation = "BUY"
    elif reduce_score >= 3 and reduce_score > buy_score:
        recommendation = "REDUCE"
    else:
        recommendation = "HOLD"

    confidence_gap = abs(buy_score - reduce_score)
    if confidence_gap >= 4:
        confidence = "high"
    elif confidence_gap >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "buy_score": buy_score,
        "reduce_score": reduce_score,
        "reason_codes": reason_codes,
    }


def recommended_fleet_delta(row: pd.Series, config: EngineConfig = DEFAULT_CONFIG) -> int:
    recommendation = row["recommendation"]
    fleet_size = int(round(float(row["fleet_size"])))
    target_fleet = int(row["target_fleet_at_85_util"])
    raw_delta = target_fleet - fleet_size

    if recommendation == "BUY":
        directional_delta = max(1, raw_delta)
    elif recommendation == "REDUCE":
        directional_delta = min(-1, raw_delta)
    else:
        return 0

    max_delta_abs = max(1, round(fleet_size * config.max_delta_pct))
    capped_delta = max(-max_delta_abs, min(max_delta_abs, directional_delta))

    if capped_delta < 0:
        max_reduction = max(0, fleet_size - config.minimum_fleet_size)
        capped_delta = max(capped_delta, -max_reduction)

    return int(capped_delta)
