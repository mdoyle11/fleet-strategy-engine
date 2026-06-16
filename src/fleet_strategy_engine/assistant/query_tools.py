from typing import Any, Optional

import pandas as pd


TEXT_FILTERS = {"station", "region", "segment", "recommendation", "confidence"}
NUMERIC_FILTERS = {
    "utilization_pct",
    "daily_roi",
    "daily_margin",
    "price_gap_pct",
    "market_share_pct",
    "recommendation_score",
    "recommended_fleet_delta",
}
QUERY_COLUMNS = [
    "station",
    "region",
    "segment",
    "fleet_size",
    "utilization_pct",
    "daily_margin",
    "daily_roi",
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


class QueryToolError(ValueError):
    pass


def compact_summary(df: pd.DataFrame) -> dict[str, Any]:
    counts = df["recommendation"].value_counts() if "recommendation" in df else {}
    return {
        "visible_rows": int(len(df)),
        "station_count": int(df["station"].nunique()) if "station" in df else 0,
        "segment_count": int(df["segment"].nunique()) if "segment" in df else 0,
        "recommendation_counts": {
            action: int(counts.get(action, 0)) for action in ("BUY", "HOLD", "REDUCE")
        },
        "net_recommended_fleet_delta": int(df["recommended_fleet_delta"].sum())
        if "recommended_fleet_delta" in df
        else 0,
        "avg_utilization_pct": safe_mean(df, "utilization_pct"),
        "avg_daily_roi": safe_mean(df, "daily_roi"),
        "avg_market_share_pct": safe_mean(df, "market_share_pct"),
    }


def safe_mean(df: pd.DataFrame, column: str) -> float:
    if column not in df or df.empty:
        return 0.0
    return round(float(df[column].mean()), 4)


def available_values(df: pd.DataFrame) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for column in TEXT_FILTERS:
        if column in df:
            values[column] = sorted(df[column].dropna().astype(str).unique().tolist())
    return values


def planning_context(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "filtered_summary": compact_summary(df),
        "available_values": available_values(df),
        "available_tools": ["lookup_opportunity", "query_opportunities", "none"],
        "allowed_text_filters": sorted(TEXT_FILTERS),
        "allowed_numeric_filters": sorted(NUMERIC_FILTERS),
        "sort_fields": sorted(NUMERIC_FILTERS | {"station", "region", "segment"}),
    }


def normalize_text_filter(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def apply_text_filter(df: pd.DataFrame, column: str, value: Any) -> pd.DataFrame:
    values = normalize_text_filter(value)
    if not values:
        return df
    wanted = {item.lower() for item in values}
    return df[df[column].astype(str).str.lower().isin(wanted)]


def apply_numeric_filter(df: pd.DataFrame, column: str, raw_filter: Any) -> pd.DataFrame:
    if raw_filter is None:
        return df
    if not isinstance(raw_filter, dict):
        raise QueryToolError(f"{column} filter must be an object with min and/or max")
    filtered = df
    if raw_filter.get("min") is not None:
        filtered = filtered[filtered[column] >= float(raw_filter["min"])]
    if raw_filter.get("max") is not None:
        filtered = filtered[filtered[column] <= float(raw_filter["max"])]
    return filtered


def query_opportunities(
    df: pd.DataFrame,
    filters: Optional[dict[str, Any]] = None,
    sort_by: Optional[str] = None,
    sort_direction: str = "desc",
    limit: int = 20,
) -> dict[str, Any]:
    filters = filters or {}
    unsupported = sorted(set(filters) - (TEXT_FILTERS | NUMERIC_FILTERS))
    if unsupported:
        raise QueryToolError(f"Unsupported query filters: {', '.join(unsupported)}")

    queried = df.copy()
    for column in TEXT_FILTERS:
        if column in filters:
            queried = apply_text_filter(queried, column, filters[column])
    for column in NUMERIC_FILTERS:
        if column in filters:
            queried = apply_numeric_filter(queried, column, filters[column])

    if sort_by:
        if sort_by not in set(queried.columns):
            raise QueryToolError(f"Unsupported sort field: {sort_by}")
        queried = queried.sort_values(
            sort_by,
            ascending=sort_direction.lower() == "asc",
        )

    row_limit = max(1, min(int(limit), 50))
    result_rows = queried.head(row_limit)
    return {
        "tool": "query_opportunities",
        "filters": filters,
        "sort_by": sort_by,
        "sort_direction": sort_direction,
        "matched_row_count": int(len(queried)),
        "returned_row_count": int(len(result_rows)),
        "summary": compact_summary(queried),
        "rows": result_rows[[column for column in QUERY_COLUMNS if column in result_rows]].to_dict(
            orient="records"
        ),
    }


def lookup_opportunity(df: pd.DataFrame, station: str, segment: str) -> dict[str, Any]:
    if not station or not segment:
        raise QueryToolError("lookup_opportunity requires station and segment")
    matches = df[
        (df["station"].astype(str).str.upper() == station.upper())
        & (df["segment"].astype(str).str.lower() == segment.lower())
    ]
    return {
        "tool": "lookup_opportunity",
        "station": station,
        "segment": segment,
        "matched_row_count": int(len(matches)),
        "summary": compact_summary(matches),
        "rows": matches[[column for column in QUERY_COLUMNS if column in matches]].to_dict(
            orient="records"
        ),
    }


def run_query_tool(df: pd.DataFrame, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "lookup_opportunity":
        return lookup_opportunity(
            df,
            str(arguments.get("station", "")),
            str(arguments.get("segment", "")),
        )
    if tool_name == "query_opportunities":
        return query_opportunities(
            df,
            arguments.get("filters", {}),
            arguments.get("sort_by"),
            str(arguments.get("sort_direction", "desc")),
            int(arguments.get("limit", 20)),
        )
    if tool_name == "none":
        return {"tool": "none", "arguments": arguments}
    raise QueryToolError(f"Unsupported query tool: {tool_name}")
