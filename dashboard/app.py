import json
from io import StringIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from fleet_strategy_engine.pipeline import run_recommendation_pipeline
from fleet_strategy_engine.pipeline.validate import ValidationError


SAMPLE_DATA_PATH = Path("data/sample_data.csv")
ACTION_ORDER = ["BUY", "HOLD", "REDUCE"]
ACTION_COLORS = {
    "BUY": "#1f9d55",
    "HOLD": "#64748b",
    "REDUCE": "#dc2626",
}


st.set_page_config(
    page_title="Fleet Strategy Engine",
    page_icon="",
    layout="wide",
)


def load_sample_data() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_DATA_PATH)


def run_pipeline(input_df: pd.DataFrame) -> None:
    recommendations, summary = run_recommendation_pipeline(input_df)
    st.session_state["input_df"] = input_df
    st.session_state["recommendations"] = recommendations
    st.session_state["summary"] = summary


def recommendation_counts_frame(df: pd.DataFrame) -> pd.DataFrame:
    counts = df["recommendation"].value_counts().reindex(ACTION_ORDER, fill_value=0)
    return counts.rename_axis("recommendation").reset_index(name="count")


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar:
        st.header("Filters")
        stations = st.multiselect("Station", sorted(df["station"].unique()))
        segments = st.multiselect("Segment", sorted(df["segment"].unique()))
        recommendations = st.multiselect("Recommendation", ACTION_ORDER)
        confidences = st.multiselect("Confidence", ["high", "medium", "low"])

    filtered = df.copy()
    if stations:
        filtered = filtered[filtered["station"].isin(stations)]
    if segments:
        filtered = filtered[filtered["segment"].isin(segments)]
    if recommendations:
        filtered = filtered[filtered["recommendation"].isin(recommendations)]
    if confidences:
        filtered = filtered[filtered["confidence"].isin(confidences)]
    return filtered


def render_summary(summary: dict, filtered_df: pd.DataFrame) -> None:
    counts = summary["recommendation_counts"]
    row1 = st.columns(4)
    row1[0].metric("Rows", f"{summary['row_count']:,}")
    row1[1].metric("Stations", f"{summary['station_count']:,}")
    row1[2].metric("Segments", f"{summary['segment_count']:,}")
    row1[3].metric("Visible Rows", f"{len(filtered_df):,}")

    row2 = st.columns(5)
    row2[0].metric("BUY", f"{counts['BUY']:,}")
    row2[1].metric("HOLD", f"{counts['HOLD']:,}")
    row2[2].metric("REDUCE", f"{counts['REDUCE']:,}")
    row2[3].metric("Net Fleet Delta", f"{summary['net_recommended_fleet_delta']:+,}")
    row2[4].metric("Avg Margin", f"${summary['avg_daily_margin']:,.2f}")


def render_charts(df: pd.DataFrame) -> None:
    left, right = st.columns(2)

    # Recommendation Counts
    counts = recommendation_counts_frame(df)
    left.plotly_chart(
        px.bar(
            counts,
            x="recommendation",
            y="count",
            color="recommendation",
            color_discrete_map=ACTION_COLORS,
            category_orders={"recommendation": ACTION_ORDER},
            labels={"recommendation": "Action", "count": "Rows"},
        ),
        use_container_width=True,
    )

    # Reason Code Counts
    reason_counts = (
        df["reason_codes"]
        .str.split("|")
        .explode()
        .value_counts()
        .head(10)
        .rename_axis("reason_code")
        .reset_index(name="count")
    )
    right.plotly_chart(
        px.bar(
            reason_counts,
            x="count",
            y="reason_code",
            orientation="h",
            labels={"reason_code": "Reason Code", "count": "Rows"},
        ),
        use_container_width=True,
    )

    scatter_left, scatter_right = st.columns(2)

    # Price Gap vs Utilization
    price_util_fig = px.scatter(
        df,
        x="price_gap_pct",
        y="utilization_pct",
        color="recommendation_score",
        color_continuous_scale=["#dc2626", "#94a3b8", "#1f9d55"],
        range_color=[-1, 1],
        hover_data=[
            "station",
            "segment",
            "recommendation",
            "confidence",
            "daily_margin",
            "market_share_pct",
            "recommended_fleet_delta",
            "pricing_signal",
            "reason_codes",
        ],
        labels={
            "price_gap_pct": "Price Gap vs Competitor %",
            "utilization_pct": "Utilization %",
            "recommendation_score": "Recommendation Signal",
        },
    )
    price_util_fig.add_hline(y=75, line_dash="dash", line_color="#94a3b8")
    price_util_fig.add_hline(y=90, line_dash="dash", line_color="#94a3b8")
    price_util_fig.add_vline(x=-10, line_dash="dash", line_color="#94a3b8")
    price_util_fig.add_vline(x=0, line_dash="dot", line_color="#94a3b8")
    scatter_left.plotly_chart(price_util_fig, use_container_width=True)

    # Utilization vs Market Share
    util_share_fig = px.scatter(
        df,
        x="utilization_pct",
        y="market_share_pct",
        color="recommendation_score",
        color_continuous_scale=["#dc2626", "#94a3b8", "#1f9d55"],
        range_color=[-1, 1],
        hover_data=[
            "station",
            "segment",
            "recommendation",
            "confidence",
            "daily_margin",
            "price_gap_pct",
            "recommended_fleet_delta",
            "pricing_signal",
            "reason_codes",
        ],
        labels={
            "utilization_pct": "Utilization %",
            "market_share_pct": "Market Share %",
            "recommendation_score": "Recommendation Signal",
        },
    )
    util_share_fig.add_vline(x=75, line_dash="dash", line_color="#94a3b8")
    util_share_fig.add_vline(x=90, line_dash="dash", line_color="#94a3b8")
    util_share_fig.add_hline(y=9, line_dash="dash", line_color="#94a3b8")
    util_share_fig.add_hline(y=15, line_dash="dash", line_color="#94a3b8")
    scatter_right.plotly_chart(util_share_fig, use_container_width=True)

    bottom_left, bottom_right = st.columns(2)

    # Utilization vs Daily Margin
    bottom_left.plotly_chart(
        px.scatter(
            df,
            x="utilization_pct",
            y="daily_margin",
            color="recommendation",
            hover_data=[
                "station",
                "segment",
                "recommendation_score",
                "market_share_pct",
                "price_gap_pct",
                "pricing_signal",
                "recommended_fleet_delta",
            ],
            color_discrete_map=ACTION_COLORS,
            category_orders={"recommendation": ACTION_ORDER},
            labels={
                "utilization_pct": "Utilization %",
                "daily_margin": "Daily Margin",
                "recommendation": "Action",
            },
        ),
        use_container_width=True,
    )

    # Net Fleet Delta By Station
    station_delta = (
        df.groupby("station", as_index=False)["recommended_fleet_delta"]
        .sum()
        .sort_values("recommended_fleet_delta", ascending=False)
    )
    bottom_right.plotly_chart(
        px.bar(
            station_delta.head(25),
            x="station",
            y="recommended_fleet_delta",
            labels={"station": "Station", "recommended_fleet_delta": "Net Fleet Delta"},
        ),
        use_container_width=True,
    )


def render_table(df: pd.DataFrame) -> None:
    columns = [
        "station",
        "segment",
        "fleet_size",
        "utilization_pct",
        "daily_margin",
        "price_gap_pct",
        "market_share_pct",
        "recommendation",
        "recommendation_score",
        "confidence",
        "pricing_signal",
        "recommended_fleet_delta",
        "reasoning",
    ]
    st.dataframe(
        df[columns],
        width="stretch",
        hide_index=True,
        column_config={
            "daily_margin": st.column_config.NumberColumn("daily_margin", format="$%.2f"),
            "price_gap_pct": st.column_config.NumberColumn("price_gap_pct", format="%.1f%%"),
            "utilization_pct": st.column_config.NumberColumn("utilization_pct", format="%.1f%%"),
            "market_share_pct": st.column_config.NumberColumn("market_share_pct", format="%.1f%%"),
            "recommended_fleet_delta": st.column_config.NumberColumn(
                "recommended_fleet_delta",
                format="%+d",
            ),
            "recommendation_score": st.column_config.ProgressColumn(
                "recommendation_score",
                min_value=-1.0,
                max_value=1.0,
                format="%.2f",
            ),
        },
    )


def render_drilldown(df: pd.DataFrame) -> None:
    st.subheader("Station Segment Drilldown")
    choices = (
        df.assign(label=lambda data: data["station"] + " / " + data["segment"])
        .sort_values("label")
        .reset_index(drop=True)
    )
    if choices.empty:
        st.info("No rows match the current filters.")
        return

    selected = st.selectbox("Select row", choices["label"])
    row = choices.loc[choices["label"] == selected].iloc[0]

    top = st.columns(5)
    top[0].metric("Action", row["recommendation"])
    top[1].metric("Confidence", row["confidence"])
    top[2].metric("Signal", f"{row['recommendation_score']:+.2f}")
    top[3].metric("Delta", f"{int(row['recommended_fleet_delta']):+}")
    top[4].metric("Utilization", f"{row['utilization_pct']:.1f}%")

    bottom = st.columns(4)
    bottom[0].metric("Daily Margin", f"${row['daily_margin']:.2f}")
    bottom[1].metric("Price Gap", f"{row['price_gap_pct']:.1f}%")
    bottom[2].metric("Market Share", f"{row['market_share_pct']:.1f}%")
    bottom[3].metric("Target Fleet", f"{int(row['target_fleet_at_85_util']):,}")

    st.write(row["reasoning"])


def render_downloads(df: pd.DataFrame, summary: dict) -> None:
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    summary_json = json.dumps(summary, indent=2)
    records_json = df.to_json(orient="records", indent=2)

    left, middle, right = st.columns(3)
    left.download_button(
        "Download recommendations CSV",
        data=csv_buffer.getvalue(),
        file_name="recommendations.csv",
        mime="text/csv",
    )
    middle.download_button(
        "Download recommendations JSON",
        data=records_json,
        file_name="recommendations.json",
        mime="application/json",
    )
    right.download_button(
        "Download summary JSON",
        data=summary_json,
        file_name="summary.json",
        mime="application/json",
    )


st.title("Fleet Strategy Engine")

with st.sidebar:
    st.header("Run")
    uploaded = st.file_uploader("Upload fleet performance CSV", type=["csv"])
    use_sample = st.button("Load Sample Data", width="stretch")
    run_uploaded = st.button(
        "Run Recommendation",
        type="primary",
        width="stretch",
        disabled=uploaded is None,
    )

if use_sample:
    try:
        run_pipeline(load_sample_data())
        st.success("Sample data processed.")
    except (ValidationError, FileNotFoundError) as exc:
        st.error(str(exc))

if run_uploaded and uploaded is not None:
    try:
        run_pipeline(pd.read_csv(uploaded))
        st.success("Uploaded data processed.")
    except ValidationError as exc:
        st.error(f"Validation failed: {exc}")
    except Exception as exc:
        st.error(f"Could not process file: {exc}")

if "recommendations" not in st.session_state:
    st.info("Upload a CSV or load sample data to generate recommendations.")
    st.stop()

recommendations_df = st.session_state["recommendations"]
summary_data = st.session_state["summary"]
filtered_df = apply_filters(recommendations_df)

render_summary(summary_data, filtered_df)

tabs = st.tabs(["Recommendations", "Charts", "Drilldown", "Downloads"])
with tabs[0]:
    render_table(filtered_df)
with tabs[1]:
    if filtered_df.empty:
        st.info("No rows match the current filters.")
    else:
        render_charts(filtered_df)
with tabs[2]:
    render_drilldown(filtered_df)
with tabs[3]:
    render_downloads(recommendations_df, summary_data)
