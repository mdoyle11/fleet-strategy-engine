from typing import Any, Optional

import pandas as pd


ACTION_ORDER = ("BUY", "HOLD", "REDUCE")
ASSISTANT_TEXT_FILTERS = {"station", "region", "segment", "recommendation", "confidence"}
ASSISTANT_NUMERIC_FILTERS = {
    "utilization_pct",
    "daily_roi",
    "daily_margin",
    "estimated_daily_profit",
    "price_gap_pct",
    "market_share_pct",
    "recommendation_score",
    "recommended_fleet_delta",
}
ASSISTANT_ROW_COLUMNS = [
    "station",
    "region",
    "segment",
    "fleet_size",
    "utilization_pct",
    "daily_margin",
    "daily_roi",
    "estimated_daily_profit",
    "price_gap_pct",
    "market_share_pct",
    "recommendation",
    "recommendation_score",
    "confidence",
    "recommended_fleet_delta",
    "pricing_signal",
    "reason_codes",
    "reasoning",
]


def recommendation_counts(df: pd.DataFrame) -> dict[str, int]:
    counts = df["recommendation"].value_counts() if "recommendation" in df else {}
    return {action: int(counts.get(action, 0)) for action in ACTION_ORDER}


def safe_mean(df: pd.DataFrame, column: str, digits: int = 4) -> float:
    if column not in df or df.empty:
        return 0.0
    return round(float(df[column].mean()), digits)


def safe_sum(df: pd.DataFrame, column: str, digits: int = 2) -> float:
    if column not in df or df.empty:
        return 0.0
    return round(float(df[column].sum()), digits)


def portfolio_summary(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "visible_rows": int(len(df)),
        "station_count": int(df["station"].nunique()) if "station" in df else 0,
        "segment_count": int(df["segment"].nunique()) if "segment" in df else 0,
        "recommendation_counts": recommendation_counts(df),
        "net_recommended_fleet_delta": int(df["recommended_fleet_delta"].sum())
        if "recommended_fleet_delta" in df
        else 0,
        "avg_utilization_pct": safe_mean(df, "utilization_pct"),
        "avg_daily_margin": safe_mean(df, "daily_margin", digits=2),
        "avg_daily_roi": safe_mean(df, "daily_roi"),
        "total_estimated_daily_profit": safe_sum(df, "estimated_daily_profit"),
        "avg_market_share_pct": safe_mean(df, "market_share_pct"),
    }


def existing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [column for column in columns if column in df]


def context_rows(
    df: pd.DataFrame,
    columns: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    selected_columns = existing_columns(df, columns or ASSISTANT_ROW_COLUMNS)
    return df[selected_columns].to_dict(orient="records")


def compact_recommendation_row(row: pd.Series) -> dict[str, Any]:
    return {
        "station": row["station"],
        "segment": row["segment"],
        "fleet_size": int(round(float(row["fleet_size"]))),
        "utilization_pct": round(float(row["utilization_pct"]), 2),
        "avg_daily_rate": round(float(row["avg_daily_rate"]), 2),
        "avg_daily_fleet_cost": round(float(row["avg_daily_fleet_cost"]), 2),
        "avg_daily_operating_cost": round(float(row["avg_daily_operating_cost"]), 2),
        "competitor_rate": round(float(row["competitor_rate"]), 2),
        "market_share_pct": round(float(row["market_share_pct"]), 2),
        "daily_margin": round(float(row["daily_margin"]), 2),
        "daily_roi": round(float(row["daily_roi"]), 4),
        "estimated_daily_profit": round(float(row["estimated_daily_profit"]), 2),
        "price_gap_pct": round(float(row["price_gap_pct"]), 2),
        "recommendation": row["recommendation"],
        "recommendation_score": round(float(row["recommendation_score"]), 2),
        "confidence": row["confidence"],
        "recommended_fleet_delta": int(row["recommended_fleet_delta"]),
        "reason_codes": row["reason_codes"],
        "reasoning": row["reasoning"],
    }


def reason_code_set(value: object) -> set[str]:
    if isinstance(value, str):
        return {item for item in value.split("|") if item}
    if isinstance(value, list):
        return {str(item) for item in value}
    return set()
