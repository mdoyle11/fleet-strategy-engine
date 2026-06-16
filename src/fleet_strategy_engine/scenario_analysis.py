from typing import Any, Optional

import pandas as pd

from fleet_strategy_engine.config import DEFAULT_CONFIG, EngineConfig
from fleet_strategy_engine.engine.explain import add_explanations
from fleet_strategy_engine.engine.recommend import add_recommendations
from fleet_strategy_engine.pipeline.features import add_features
from fleet_strategy_engine.pipeline.validate import validate_input
from fleet_strategy_engine.schemas import REQUIRED_COLUMNS


DOWNSIDE_CASES = {
    "mild": {
        "utilization_pct_delta": -2.0,
        "market_share_pct_delta": -1.0,
        "avg_daily_fleet_cost_pct_delta": 0.05,
    },
    "moderate": {
        "utilization_pct_delta": -4.0,
        "market_share_pct_delta": -2.0,
        "avg_daily_fleet_cost_pct_delta": 0.10,
    },
    "severe": {
        "utilization_pct_delta": -7.0,
        "market_share_pct_delta": -4.0,
        "avg_daily_fleet_cost_pct_delta": 0.15,
    },
}


def run_recommendations(df: pd.DataFrame, config: EngineConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    input_df = df[REQUIRED_COLUMNS].copy()
    validate_input(input_df)
    featured = add_features(input_df, config)
    recommended = add_recommendations(featured, config)
    return add_explanations(recommended)


def score_margin_to_action_threshold(score: float) -> float:
    if score >= 0.35:
        return round(score - 0.35, 2)
    if score <= -0.35:
        return round(abs(score + 0.35), 2)
    return round(min(0.35 - score, score + 0.35), 2)


def threshold_proximity(row: pd.Series, config: EngineConfig) -> tuple[str, float]:
    daily_roi_pct = float(row["daily_roi"]) * 100
    thresholds = [
        ("utilization to 70%", abs(float(row["utilization_pct"]) - 70)),
        (
            f"utilization to {config.underutilized_pct:.1f}%",
            abs(float(row["utilization_pct"]) - config.underutilized_pct),
        ),
        ("utilization to 88%", abs(float(row["utilization_pct"]) - 88)),
        (
            f"utilization to {config.high_utilization_pct:.1f}%",
            abs(float(row["utilization_pct"]) - config.high_utilization_pct),
        ),
        (
            f"ROI to {config.thin_roi_threshold:.0%}",
            abs(daily_roi_pct - config.thin_roi_threshold * 100),
        ),
        (
            f"ROI to {config.strong_roi_threshold:.0%}",
            abs(daily_roi_pct - config.strong_roi_threshold * 100),
        ),
        (
            f"market share to {config.weak_market_share_pct:.1f}%",
            abs(float(row["market_share_pct"]) - config.weak_market_share_pct),
        ),
        (
            f"market share to {config.strong_market_share_pct:.1f}%",
            abs(float(row["market_share_pct"]) - config.strong_market_share_pct),
        ),
        ("price gap to -10%", abs(float(row["price_gap_pct"]) + 10)),
        ("price gap to +5%", abs(float(row["price_gap_pct"]) - 5)),
        ("price gap to +10%", abs(float(row["price_gap_pct"]) - 10)),
    ]
    return min(thresholds, key=lambda item: item[1])


def add_fragility_columns(df: pd.DataFrame, config: EngineConfig) -> pd.DataFrame:
    fragile = df.copy()
    proximity = fragile.apply(lambda row: threshold_proximity(row, config), axis=1)
    fragile["nearest_rule_threshold"] = [item[0] for item in proximity]
    fragile["nearest_threshold_distance"] = [round(float(item[1]), 2) for item in proximity]
    fragile["score_margin_to_action_change"] = fragile["recommendation_score"].apply(
        score_margin_to_action_threshold
    )
    return fragile


def scenario_label(row: pd.Series) -> str:
    if row["recommendation"] == row["scenario_recommendation"]:
        return "Stable"
    return f"{row['recommendation']} -> {row['scenario_recommendation']}"


def compare_rule_outputs(
    baseline: pd.DataFrame,
    scenario: pd.DataFrame,
    include_reasoning: bool = False,
) -> pd.DataFrame:
    scenario_columns = [
        "station",
        "segment",
        "recommendation",
        "recommendation_score",
        "confidence",
        "recommended_fleet_delta",
        "reason_codes",
    ]
    if include_reasoning:
        scenario_columns.append("reasoning")

    rename_columns = {
        "recommendation": "scenario_recommendation",
        "recommendation_score": "scenario_recommendation_score",
        "confidence": "scenario_confidence",
        "recommended_fleet_delta": "scenario_recommended_fleet_delta",
        "reason_codes": "scenario_reason_codes",
        "reasoning": "scenario_reasoning",
    }
    comparison = baseline.merge(
        scenario[scenario_columns].rename(columns=rename_columns),
        on=["station", "segment"],
        how="left",
    )
    comparison["scenario_change"] = comparison.apply(scenario_label, axis=1)
    comparison["score_change"] = (
        comparison["scenario_recommendation_score"] - comparison["recommendation_score"]
    )
    comparison["delta_change"] = (
        comparison["scenario_recommended_fleet_delta"]
        - comparison["recommended_fleet_delta"]
    )
    comparison["absolute_score_change"] = comparison["score_change"].abs()
    comparison["baseline_score_margin"] = comparison["recommendation_score"].apply(
        score_margin_to_action_threshold
    )
    return comparison


def fragile_recommendations(
    df: pd.DataFrame,
    limit: int = 10,
    recommendation_filter: Optional[str] = None,
) -> pd.DataFrame:
    recommended = run_recommendations(df, DEFAULT_CONFIG)
    fragile = add_fragility_columns(recommended, DEFAULT_CONFIG)
    if recommendation_filter:
        action = recommendation_filter.upper()
        if action not in {"BUY", "HOLD", "REDUCE"}:
            raise ValueError("recommendation_filter must be BUY, HOLD, or REDUCE")
        fragile = fragile[fragile["recommendation"] == action]

    return fragile.sort_values(
        [
            "score_margin_to_action_change",
            "nearest_threshold_distance",
            "confidence",
            "station",
            "segment",
        ]
    ).head(max(1, int(limit)))


def downside_updates(row: pd.Series, downside_case: str) -> dict[str, float]:
    case = DOWNSIDE_CASES.get(downside_case.lower())
    if case is None:
        raise ValueError("downside_case must be one of: " + ", ".join(sorted(DOWNSIDE_CASES)))
    return {
        "utilization_pct": max(
            0.0,
            min(100.0, float(row["utilization_pct"]) + case["utilization_pct_delta"]),
        ),
        "market_share_pct": max(
            0.0,
            min(100.0, float(row["market_share_pct"]) + case["market_share_pct_delta"]),
        ),
        "avg_daily_fleet_cost": max(
            0.0,
            float(row["avg_daily_fleet_cost"])
            * (1 + case["avg_daily_fleet_cost_pct_delta"]),
        ),
    }


def rerun_single_row(row: pd.Series, updates: dict[str, float]) -> pd.Series:
    input_row = row[REQUIRED_COLUMNS].copy()
    for column, value in updates.items():
        input_row[column] = value
    result = run_recommendations(pd.DataFrame([input_row]), DEFAULT_CONFIG)
    return result.iloc[0]


def metric_step(column: str) -> float:
    if column == "fleet_size":
        return 1.0
    if column in {"utilization_pct", "market_share_pct"}:
        return 0.5
    return 1.0


def metric_bounds(column: str, value: float) -> tuple[float, float]:
    if column == "fleet_size":
        return 1.0, max(1.0, value * 2)
    if column == "utilization_pct":
        return 1.0, 100.0
    if column == "market_share_pct":
        return 0.0, 40.0
    if column == "competitor_rate":
        return 1.0, max(1.0, value * 2)
    return 0.0, max(1.0, value * 2)


def find_metric_flip(row: pd.Series, column: str, metric_label: str) -> dict[str, Any]:
    current_value = float(row[column])
    current_recommendation = row["recommendation"]
    lower, upper = metric_bounds(column, current_value)
    step = metric_step(column)
    candidates = []

    low_steps = int(max(0, (current_value - lower) / step))
    high_steps = int(max(0, (upper - current_value) / step))
    for offset in range(1, max(low_steps, high_steps) + 1):
        for direction in (-1, 1):
            candidate = current_value + direction * offset * step
            if candidate < lower or candidate > upper:
                continue
            if column == "fleet_size":
                candidate = int(round(candidate))
            scenario = rerun_single_row(row, {column: candidate})
            if scenario["recommendation"] != current_recommendation:
                candidates.append(
                    {
                        "metric": metric_label,
                        "current_value": current_value,
                        "flip_value": candidate,
                        "change_needed": candidate - current_value,
                        "new_recommendation": scenario["recommendation"],
                        "new_score": scenario["recommendation_score"],
                    }
                )
        if candidates:
            break

    if not candidates:
        return {
            "metric": metric_label,
            "current_value": current_value,
            "flip_value": None,
            "change_needed": None,
            "new_recommendation": "No flip in tested range",
            "new_score": None,
        }
    return min(candidates, key=lambda item: abs(float(item["change_needed"])))
