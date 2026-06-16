import pandas as pd
import streamlit as st

from dashboard.common import filtered_counts, render_colored_metric
from dashboard.constants import ACTION_COLORS, ACTION_ORDER, REGION_ORDER


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar:
        st.header("Filters")
        regions = st.multiselect(
            "Region",
            [region for region in REGION_ORDER if region in set(df["region"])],
        )
        stations = st.multiselect("Station", sorted(df["station"].unique()))
        segments = st.multiselect("Segment", sorted(df["segment"].unique()))
        recommendations = st.multiselect("Recommendation", ACTION_ORDER)
        confidences = st.multiselect("Confidence", ["high", "medium", "low"])

    filtered = df.copy()
    if regions:
        filtered = filtered[filtered["region"].isin(regions)]
    if stations:
        filtered = filtered[filtered["station"].isin(stations)]
    if segments:
        filtered = filtered[filtered["segment"].isin(segments)]
    if recommendations:
        filtered = filtered[filtered["recommendation"].isin(recommendations)]
    if confidences:
        filtered = filtered[filtered["confidence"].isin(confidences)]
    return filtered


def render_summary(filtered_df: pd.DataFrame) -> None:
    counts = filtered_counts(filtered_df)
    avg_roi = filtered_df["daily_roi"].mean() if not filtered_df.empty else 0
    avg_utilization = filtered_df["utilization_pct"].mean() if not filtered_df.empty else 0
    avg_market_share = filtered_df["market_share_pct"].mean() if not filtered_df.empty else 0

    row1 = st.columns(4)
    row1[0].metric("Visible Rows", f"{len(filtered_df):,}")
    row1[1].metric("Stations", f"{filtered_df['station'].nunique():,}")
    row1[2].metric("Segments", f"{filtered_df['segment'].nunique():,}")
    row1[3].metric("Avg ROI", f"{avg_roi:.1%}")

    row2 = st.columns(5)
    with row2[0]:
        render_colored_metric("BUY", f"{counts['BUY']:,}", ACTION_COLORS["BUY"], "#ffffff")
    with row2[1]:
        render_colored_metric("HOLD", f"{counts['HOLD']:,}", ACTION_COLORS["HOLD"], "#ffffff")
    with row2[2]:
        render_colored_metric(
            "REDUCE",
            f"{counts['REDUCE']:,}",
            ACTION_COLORS["REDUCE"],
            "#ffffff",
        )
    row2[3].metric("Avg Utilization", f"{avg_utilization:.1f}%")
    row2[4].metric("Avg Market Share", f"{avg_market_share:.1f}%")


