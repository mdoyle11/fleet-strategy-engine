from typing import Any

import pandas as pd


def comparison_frame(
    current: pd.Series,
    scenario: pd.Series,
    columns: list[str],
) -> pd.DataFrame:
    rows = []
    for column in columns:
        current_value = current[column]
        scenario_value = scenario[column]
        if isinstance(current_value, str) or isinstance(scenario_value, str):
            change = "changed" if current_value != scenario_value else "same"
        else:
            change = float(scenario_value) - float(current_value)
        rows.append(
            {
                "Metric": column,
                "Current": format_comparison_value(column, current_value),
                "What-If": format_comparison_value(column, scenario_value),
                "Change": format_comparison_change(column, change),
            }
        )
    return pd.DataFrame(rows)


def format_comparison_value(column: str, value: object) -> str:
    if isinstance(value, str):
        return value
    numeric_value = float(value)
    if column in {"daily_margin", "estimated_daily_profit"}:
        return f"${numeric_value:,.2f}"
    if column in {"daily_roi"}:
        return f"{numeric_value:.1%}"
    if column in {"utilization_pct", "market_share_pct", "price_gap_pct"}:
        return f"{numeric_value:.1f}%"
    if column in {"recommendation_score"}:
        return f"{numeric_value:+.2f}"
    if column in {"fleet_size", "recommended_fleet_delta"}:
        return (
            f"{int(round(numeric_value)):+d}"
            if column.endswith("_delta")
            else f"{int(round(numeric_value)):,}"
        )
    return f"{numeric_value:,.2f}"


def format_comparison_change(column: str, value: Any) -> str:
    if isinstance(value, str):
        return value
    numeric_value = float(value)
    if column in {"daily_margin", "estimated_daily_profit"}:
        return f"{numeric_value:+,.2f}"
    if column in {"daily_roi"}:
        return f"{numeric_value:+.1%}"
    if column in {"utilization_pct", "market_share_pct", "price_gap_pct"}:
        return f"{numeric_value:+.1f} pts"
    if column in {"recommendation_score"}:
        return f"{numeric_value:+.2f}"
    if column in {"fleet_size", "recommended_fleet_delta"}:
        return f"{int(round(numeric_value)):+d}"
    return f"{numeric_value:+,.2f}"
