import pandas as pd
import streamlit as st

from dashboard.constants import ACTION_ORDER
from fleet_strategy_engine.geography import station_region
from fleet_strategy_engine.recommendation_context import recommendation_counts


def ensure_region_column(df: pd.DataFrame) -> pd.DataFrame:
    if "region" in df.columns:
        return df

    enriched = df.copy()
    insert_at = min(1, len(enriched.columns))
    enriched.insert(
        insert_at,
        "region",
        enriched["station"].apply(station_region),
    )
    return enriched


def filtered_counts(df: pd.DataFrame) -> dict[str, int]:
    counts = recommendation_counts(df)
    return {action: counts[action] for action in ACTION_ORDER}


def render_colored_metric(
    label: str,
    value: str,
    value_color: str,
    label_color: str = "rgba(49, 51, 63, 0.6)",
) -> None:
    st.markdown(
        f"""
        <div data-testid="stMetric">
            <label data-testid="stMetricLabel">
                <div style="color: {label_color}; font-size: 0.875rem;">
                    {label}
                </div>
            </label>
            <div data-testid="stMetricValue" style="
                color: {value_color};
                font-size: 2rem;
                line-height: 1.2;
                font-weight: 400;
            ">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

