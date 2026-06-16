from dataclasses import replace
from typing import Any, Optional

import pandas as pd

from fleet_strategy_engine.config import DEFAULT_CONFIG, EngineConfig
from fleet_strategy_engine.recommendation_context import (
    compact_recommendation_row,
    reason_code_set,
    recommendation_counts,
)
from fleet_strategy_engine.scenario_analysis import (
    add_fragility_columns,
    compare_rule_outputs,
    downside_updates as build_downside_updates,
    fragile_recommendations as build_fragile_recommendations,
    run_recommendations,
)
from fleet_strategy_engine.schemas import REQUIRED_COLUMNS


RULE_FIELD_BOUNDS = {
    "target_utilization": (0.75, 0.95),
    "max_delta_pct": (0.05, 0.40),
    "weak_market_share_pct": (4.0, 14.0),
    "strong_market_share_pct": (10.0, 25.0),
    "underutilized_pct": (65.0, 82.0),
    "high_utilization_pct": (84.0, 96.0),
    "thin_roi_threshold": (0.05, 0.50),
    "strong_roi_threshold": (0.40, 1.20),
}
METRIC_FIELD_BOUNDS = {
    "fleet_size": (1.0, None),
    "utilization_pct": (0.0, 100.0),
    "avg_daily_rate": (0.0, None),
    "avg_daily_fleet_cost": (0.0, None),
    "avg_daily_operating_cost": (0.0, None),
    "competitor_rate": (0.01, None),
    "market_share_pct": (0.0, 100.0),
}


class ScenarioToolError(ValueError):
    pass


def bounded_updates(
    updates: dict[str, Any],
    bounds: dict[str, tuple[float, Optional[float]]],
) -> dict[str, float]:
    clean: dict[str, float] = {}
    unsupported = sorted(set(updates) - set(bounds))
    if unsupported:
        raise ScenarioToolError(f"Unsupported scenario fields: {', '.join(unsupported)}")

    for field, raw_value in updates.items():
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ScenarioToolError(f"{field} must be numeric") from exc

        lower, upper = bounds[field]
        if value < lower or (upper is not None and value > upper):
            if upper is None:
                raise ScenarioToolError(f"{field} must be at least {lower:g}")
            raise ScenarioToolError(f"{field} must be between {lower:g} and {upper:g}")
        clean[field] = value
    return clean


def config_with_updates(updates: dict[str, Any]) -> EngineConfig:
    clean = bounded_updates(updates, RULE_FIELD_BOUNDS)
    if (
        "weak_market_share_pct" in clean
        and "strong_market_share_pct" in clean
        and clean["weak_market_share_pct"] >= clean["strong_market_share_pct"]
    ):
        raise ScenarioToolError("weak_market_share_pct must be below strong_market_share_pct")
    if (
        "underutilized_pct" in clean
        and "high_utilization_pct" in clean
        and clean["underutilized_pct"] >= clean["high_utilization_pct"]
    ):
        raise ScenarioToolError("underutilized_pct must be below high_utilization_pct")
    if (
        "thin_roi_threshold" in clean
        and "strong_roi_threshold" in clean
        and clean["thin_roi_threshold"] >= clean["strong_roi_threshold"]
    ):
        raise ScenarioToolError("thin_roi_threshold must be below strong_roi_threshold")
    return replace(DEFAULT_CONFIG, **clean)


def filtered_counts(df: pd.DataFrame) -> dict[str, int]:
    return recommendation_counts(df)


def fragile_recommendations(
    df: pd.DataFrame,
    limit: int = 10,
    recommendation_filter: Optional[str] = None,
) -> pd.DataFrame:
    try:
        return build_fragile_recommendations(df, limit, recommendation_filter)
    except ValueError as exc:
        raise ScenarioToolError(str(exc)) from exc


def compact_fragile_row(row: pd.Series) -> dict[str, Any]:
    return {
        "station": row["station"],
        "segment": row["segment"],
        "recommendation": row["recommendation"],
        "recommendation_score": round(float(row["recommendation_score"]), 2),
        "confidence": row["confidence"],
        "recommended_fleet_delta": int(row["recommended_fleet_delta"]),
        "score_margin_to_action_change": round(
            float(row["score_margin_to_action_change"]),
            2,
        ),
        "nearest_rule_threshold": row["nearest_rule_threshold"],
        "nearest_threshold_distance": round(float(row["nearest_threshold_distance"]), 2),
        "utilization_pct": round(float(row["utilization_pct"]), 2),
        "daily_roi": round(float(row["daily_roi"]), 4),
        "market_share_pct": round(float(row["market_share_pct"]), 2),
        "price_gap_pct": round(float(row["price_gap_pct"]), 2),
        "reason_codes": row["reason_codes"],
    }


def downside_updates(row: pd.Series, downside_case: str) -> dict[str, float]:
    try:
        return build_downside_updates(row, downside_case)
    except ValueError as exc:
        raise ScenarioToolError(str(exc)) from exc


def find_fragile_recommendations(
    df: pd.DataFrame,
    limit: int = 10,
    recommendation_filter: Optional[str] = None,
    downside_case: Optional[str] = None,
) -> dict[str, Any]:
    fragile = fragile_recommendations(df, limit, recommendation_filter)
    rows = [compact_fragile_row(row) for _, row in fragile.iterrows()]
    result: dict[str, Any] = {
        "tool": "find_fragile_recommendations",
        "limit": int(limit),
        "recommendation_filter": recommendation_filter.upper()
        if recommendation_filter
        else None,
        "downside_case": downside_case,
        "fragile_rows": rows,
    }

    if downside_case:
        downside_results = []
        for _, row in fragile.iterrows():
            updates = downside_updates(row, downside_case)
            downside_results.append(
                metric_scenario(df, row["station"], row["segment"], updates)
            )
        result["downside_results"] = downside_results
    return result


def rule_scenario(df: pd.DataFrame, updates: dict[str, Any]) -> dict[str, Any]:
    config = config_with_updates(updates)
    baseline = run_recommendations(df, DEFAULT_CONFIG)
    scenario = run_recommendations(df, config)
    comparison = compare_rule_outputs(baseline, scenario)
    changed = comparison[comparison["scenario_change"] != "Stable"].copy()
    fragile = add_fragility_columns(baseline, DEFAULT_CONFIG).sort_values(
        ["score_margin_to_action_change", "nearest_threshold_distance"]
    )

    return {
        "tool": "run_rule_scenario",
        "updates": bounded_updates(updates, RULE_FIELD_BOUNDS),
        "baseline_counts": filtered_counts(baseline),
        "scenario_counts": filtered_counts(scenario),
        "baseline_net_delta": int(baseline["recommended_fleet_delta"].sum()),
        "scenario_net_delta": int(scenario["recommended_fleet_delta"].sum()),
        "changed_row_count": int(len(changed)),
        "changed_rows": changed[
            [
                "station",
                "segment",
                "recommendation",
                "scenario_recommendation",
                "recommendation_score",
                "scenario_recommendation_score",
                "score_change",
                "recommended_fleet_delta",
                "scenario_recommended_fleet_delta",
                "delta_change",
                "scenario_change",
            ]
        ].head(20).to_dict(orient="records"),
        "fragile_rows": fragile[
            [
                "station",
                "segment",
                "recommendation",
                "recommendation_score",
                "score_margin_to_action_change",
                "nearest_rule_threshold",
                "nearest_threshold_distance",
            ]
        ].head(10).to_dict(orient="records"),
    }


def select_opportunity(df: pd.DataFrame, station: str, segment: str) -> pd.Series:
    matches = df[
        (df["station"].astype(str).str.upper() == station.upper())
        & (df["segment"].astype(str).str.lower() == segment.lower())
    ]
    if matches.empty:
        raise ScenarioToolError(f"No opportunity found for {station} / {segment}")
    if len(matches) > 1:
        raise ScenarioToolError(f"Multiple opportunities found for {station} / {segment}")
    return matches.iloc[0]


def compact_row(row: pd.Series) -> dict[str, Any]:
    return compact_recommendation_row(row)


def metric_scenario(
    df: pd.DataFrame,
    station: str,
    segment: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    clean = bounded_updates(updates, METRIC_FIELD_BOUNDS)
    baseline = run_recommendations(df, DEFAULT_CONFIG)
    base_row = select_opportunity(baseline, station, segment)
    input_row = base_row[REQUIRED_COLUMNS].copy()
    for field, value in clean.items():
        input_row[field] = int(round(value)) if field == "fleet_size" else value
    scenario_row = run_recommendations(pd.DataFrame([input_row]), DEFAULT_CONFIG).iloc[0]

    added_codes = reason_code_set(scenario_row["reason_codes"]) - reason_code_set(
        base_row["reason_codes"]
    )
    removed_codes = reason_code_set(base_row["reason_codes"]) - reason_code_set(
        scenario_row["reason_codes"]
    )
    return {
        "tool": "run_metric_scenario",
        "station": base_row["station"],
        "segment": base_row["segment"],
        "updates": clean,
        "current": compact_row(base_row),
        "scenario": compact_row(scenario_row),
        "recommendation_changed": bool(
            base_row["recommendation"] != scenario_row["recommendation"]
        ),
        "score_change": round(
            float(scenario_row["recommendation_score"])
            - float(base_row["recommendation_score"]),
            2,
        ),
        "delta_change": int(
            scenario_row["recommended_fleet_delta"] - base_row["recommended_fleet_delta"]
        ),
        "added_reason_codes": sorted(added_codes),
        "removed_reason_codes": sorted(removed_codes),
    }


def run_scenario_tool(df: pd.DataFrame, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "find_fragile_recommendations":
        return find_fragile_recommendations(
            df,
            int(arguments.get("limit", 10)),
            arguments.get("recommendation_filter"),
            arguments.get("downside_case"),
        )
    if tool_name == "run_rule_scenario":
        return rule_scenario(df, arguments.get("updates", {}))
    if tool_name == "run_metric_scenario":
        return metric_scenario(
            df,
            str(arguments.get("station", "")),
            str(arguments.get("segment", "")),
            arguments.get("updates", {}),
        )
    raise ScenarioToolError(f"Unsupported scenario tool: {tool_name}")
