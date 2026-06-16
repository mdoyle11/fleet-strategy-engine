from typing import Any, Optional

import pandas as pd

from fleet_strategy_engine.recommendation_context import (
    ASSISTANT_NUMERIC_FILTERS,
    ASSISTANT_ROW_COLUMNS,
    ASSISTANT_TEXT_FILTERS,
    context_rows,
    portfolio_summary,
)

TEXT_FILTERS = ASSISTANT_TEXT_FILTERS
NUMERIC_FILTERS = ASSISTANT_NUMERIC_FILTERS
QUERY_COLUMNS = ASSISTANT_ROW_COLUMNS


class QueryToolError(ValueError):
    pass


def compact_summary(df: pd.DataFrame) -> dict[str, Any]:
    return portfolio_summary(df)


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
        "rows": context_rows(result_rows, QUERY_COLUMNS),
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
        "rows": context_rows(matches, QUERY_COLUMNS),
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
