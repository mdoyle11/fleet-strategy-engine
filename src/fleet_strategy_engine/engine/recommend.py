from typing import Any

import pandas as pd

from fleet_strategy_engine.config import DEFAULT_CONFIG, EngineConfig


BUY_SIGNAL_THRESHOLD = 0.35
REDUCE_SIGNAL_THRESHOLD = -0.35


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
    return recommended


def score_row(row: pd.Series, config: EngineConfig = DEFAULT_CONFIG) -> dict[str, Any]:
    signal_points = 0
    reason_codes: list[str] = []

    util = float(row["utilization_pct"])
    margin = float(row["daily_margin"])
    share = float(row["market_share_pct"])
    price_gap_pct = float(row["price_gap_pct"])

    if util >= config.high_utilization_pct:
        signal_points += 3
        reason_codes.append("utilization_above_90")
    elif util >= 88:
        signal_points += 1
        reason_codes.append("utilization_near_upper_target")
    elif util < 70:
        signal_points -= 3
        reason_codes.append("utilization_below_70")
    elif util < config.underutilized_pct:
        signal_points -= 2
        reason_codes.append("utilization_below_75")
    elif 80 <= util <= 88:
        reason_codes.append("utilization_in_target_range")
    else:
        reason_codes.append("utilization_near_target")

    if margin <= 0:
        signal_points -= 3
        reason_codes.append("non_positive_margin")
    elif margin < 15:
        signal_points -= 1
        reason_codes.append("thin_margin")
    elif margin >= 40:
        signal_points += 1
        reason_codes.append("strong_margin")
    else:
        reason_codes.append("healthy_margin")

    if share >= config.strong_market_share_pct and util >= 88:
        signal_points += 2
        reason_codes.append("strong_share_and_high_utilization")
    elif share >= config.strong_market_share_pct:
        signal_points += 1
        reason_codes.append("strong_market_share")
    elif share < config.weak_market_share_pct and util < 80:
        signal_points -= 2
        reason_codes.append("weak_share_and_weak_utilization")
    elif share < config.weak_market_share_pct:
        signal_points -= 1
        reason_codes.append("weak_market_share")
    else:
        reason_codes.append("moderate_market_share")

    if price_gap_pct <= -10 and util >= config.high_utilization_pct:
        signal_points -= 1
        reason_codes.append("discounted_vs_competitor_with_high_utilization")
    elif price_gap_pct >= 5 and util >= config.high_utilization_pct:
        signal_points += 1
        reason_codes.append("above_competitor_and_still_high_utilization")
    elif price_gap_pct >= 10 and util < 80:
        signal_points -= 1
        reason_codes.append("above_competitor_with_weak_utilization")
    else:
        reason_codes.append("pricing_near_competitor")

    recommendation_score = clamp(signal_points / 6, -1, 1)
    if margin <= 0:
        recommendation_score = min(recommendation_score, BUY_SIGNAL_THRESHOLD - 0.01)

    if recommendation_score >= BUY_SIGNAL_THRESHOLD:
        recommendation = "BUY"
    elif recommendation_score <= REDUCE_SIGNAL_THRESHOLD:
        recommendation = "REDUCE"
    else:
        recommendation = "HOLD"

    directional_strength = abs(recommendation_score)
    has_conflict = has_conflicting_reason_codes(reason_codes)
    if recommendation == "HOLD" and not has_conflict:
        confidence = "high"
    elif directional_strength >= 0.70 and not has_conflict:
        confidence = "high"
    elif directional_strength >= BUY_SIGNAL_THRESHOLD:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "recommendation": recommendation,
        "recommendation_score": round(recommendation_score, 2),
        "confidence": confidence,
        "reason_codes": reason_codes,
    }


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def has_conflicting_reason_codes(reason_codes: list[str]) -> bool:
    buy_codes = {
        "utilization_above_90",
        "utilization_near_upper_target",
        "strong_margin",
        "strong_share_and_high_utilization",
        "strong_market_share",
        "above_competitor_and_still_high_utilization",
    }
    reduce_codes = {
        "utilization_below_70",
        "utilization_below_75",
        "non_positive_margin",
        "thin_margin",
        "weak_share_and_weak_utilization",
        "weak_market_share",
        "discounted_vs_competitor_with_high_utilization",
        "above_competitor_with_weak_utilization",
    }
    return bool(set(reason_codes) & buy_codes) and bool(set(reason_codes) & reduce_codes)


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
