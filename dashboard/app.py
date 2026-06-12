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
REGION_ORDER = ["Northeast", "South", "Midwest", "West", "Unknown"]
SEGMENT_ORDER = ["Economy", "SUV", "Premium", "Minivan", "Truck"]
STATION_REGION_MAP = {
    "ANC": "West",
    "ATL": "South",
    "AUS": "South",
    "BNA": "South",
    "BOS": "Northeast",
    "BWI": "South",
    "CLE": "Midwest",
    "CLT": "South",
    "CMH": "Midwest",
    "DAL": "South",
    "DEN": "West",
    "DFW": "South",
    "DTW": "Midwest",
    "EWR": "Northeast",
    "HNL": "West",
    "HOU": "South",
    "IAD": "South",
    "IAH": "South",
    "IND": "Midwest",
    "JAX": "South",
    "JFK": "Northeast",
    "LAS": "West",
    "LAX": "West",
    "LGA": "Northeast",
    "MCI": "Midwest",
    "MCO": "South",
    "MDW": "Midwest",
    "MEM": "South",
    "MIA": "South",
    "MSP": "Midwest",
    "MSY": "South",
    "OAK": "West",
    "OGG": "West",
    "OKC": "South",
    "OMA": "Midwest",
    "ORD": "Midwest",
    "PDX": "West",
    "PHL": "Northeast",
    "PHX": "West",
    "PIT": "Northeast",
    "RDU": "South",
    "SAN": "West",
    "SAT": "South",
    "SEA": "West",
    "SFO": "West",
    "SJC": "West",
    "SLC": "West",
    "SMF": "West",
    "STL": "Midwest",
    "TPA": "South",
}
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


def ensure_region_column(df: pd.DataFrame) -> pd.DataFrame:
    if "region" in df.columns:
        return df

    enriched = df.copy()
    insert_at = min(1, len(enriched.columns))
    enriched.insert(
        insert_at,
        "region",
        enriched["station"].apply(lambda station: STATION_REGION_MAP.get(str(station).upper(), "Unknown")),
    )
    return enriched


def filtered_counts(df: pd.DataFrame) -> dict[str, int]:
    counts = df["recommendation"].value_counts()
    return {action: int(counts.get(action, 0)) for action in ACTION_ORDER}


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
    avg_margin = filtered_df["daily_margin"].mean() if not filtered_df.empty else 0
    avg_utilization = filtered_df["utilization_pct"].mean() if not filtered_df.empty else 0
    avg_market_share = filtered_df["market_share_pct"].mean() if not filtered_df.empty else 0

    row1 = st.columns(4)
    row1[0].metric("Visible Rows", f"{len(filtered_df):,}")
    row1[1].metric("Stations", f"{filtered_df['station'].nunique():,}")
    row1[2].metric("Segments", f"{filtered_df['segment'].nunique():,}")
    row1[3].metric("Avg Margin", f"${avg_margin:,.2f}")

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


def action_ranking_frame(df: pd.DataFrame, action: str, limit: int = 12) -> pd.DataFrame:
    ranked = df[df["recommendation"] == action].copy()
    if ranked.empty:
        return ranked

    ranked["station_segment"] = ranked["station"] + " / " + ranked["segment"]
    if action == "BUY":
        ranked = ranked.sort_values(
            ["recommendation_score", "recommended_fleet_delta", "utilization_pct"],
            ascending=[False, False, False],
        )
    else:
        ranked = ranked.sort_values(
            ["recommendation_score", "recommended_fleet_delta", "utilization_pct"],
            ascending=[True, True, True],
        )
    return ranked.head(limit)


def render_charts(df: pd.DataFrame) -> None:
    left, right = st.columns(2)

    # Top Actionable Recommendations
    with left:
        action = st.radio(
            "Top Actionable Recommendations",
            ["BUY", "REDUCE"],
            horizontal=True,
            label_visibility="visible",
        )
        ranking = action_ranking_frame(df, action)
        if ranking.empty:
            st.info(f"No {action} recommendations match the current filters.")
        else:
            ranking_fig = px.bar(
                ranking,
                x="recommended_fleet_delta",
                y="station_segment",
                orientation="h",
                color="recommendation_score",
                color_continuous_scale=["#dc2626", "#94a3b8", "#1f9d55"],
                range_color=[-1, 1],
                hover_data=[
                    "station",
                    "region",
                    "segment",
                    "utilization_pct",
                    "daily_margin",
                    "market_share_pct",
                    "price_gap_pct",
                    "confidence",
                    "reason_codes",
                ],
                labels={
                    "station_segment": "Station / Segment",
                    "recommended_fleet_delta": "Recommended Fleet Delta",
                    "recommendation_score": "Recommendation Signal",
                },
            )
            ranking_fig.update_layout(
                title=f"Top {action} Options by Recommendation Signal",
                yaxis={
                    "categoryorder": "array",
                    "categoryarray": ranking["station_segment"].iloc[::-1].tolist(),
                    "title": "",
                },
            )
            st.plotly_chart(ranking_fig, use_container_width=True)

    # Utilization Heatmap
    utilization_matrix = (
        df.pivot_table(
            index="station",
            columns="segment",
            values="utilization_pct",
            aggfunc="mean",
        )
        .sort_index()
        .round(1)
    )
    ordered_segments = [
        segment for segment in SEGMENT_ORDER if segment in utilization_matrix.columns
    ]
    utilization_matrix = utilization_matrix[ordered_segments]
    heatmap_height = max(420, min(1100, 24 * len(utilization_matrix) + 140))
    heatmap_fig = px.imshow(
        utilization_matrix,
        aspect="auto",
        color_continuous_scale=["#dc2626", "#facc15", "#1f9d55"],
        range_color=[60, 100],
        labels={
            "x": "Segment",
            "y": "Station",
            "color": "Avg Utilization %",
        },
        text_auto=True,
    )
    heatmap_fig.update_layout(height=heatmap_height)
    heatmap_fig.update_yaxes(
        tickmode="array",
        tickvals=list(utilization_matrix.index),
        ticktext=list(utilization_matrix.index),
    )
    right.plotly_chart(heatmap_fig, use_container_width=True)

    # Net Fleet Delta By Station
    station_delta = (
        df.groupby("station", as_index=False)["recommended_fleet_delta"]
        .sum()
        .sort_values("recommended_fleet_delta", ascending=False)
    )
    station_delta["delta_direction"] = station_delta["recommended_fleet_delta"].apply(
        lambda value: "Increase" if value > 0 else "Reduction" if value < 0 else "No Change"
    )
    delta_height = max(420, min(1100, 22 * len(station_delta) + 140))
    delta_fig = px.bar(
        station_delta,
        x="recommended_fleet_delta",
        y="station",
        orientation="h",
        color="delta_direction",
        color_discrete_map={
            "Increase": ACTION_COLORS["BUY"],
            "Reduction": ACTION_COLORS["REDUCE"],
            "No Change": ACTION_COLORS["HOLD"],
        },
        category_orders={
            "station": station_delta["station"].tolist(),
            "delta_direction": ["Reduction", "No Change", "Increase"],
        },
        labels={
            "station": "Station",
            "recommended_fleet_delta": "Net Fleet Delta",
            "delta_direction": "Delta Direction",
        },
    )
    delta_fig.add_vline(x=0, line_dash="dot", line_color="#94a3b8")
    delta_fig.update_layout(
        title="Net Fleet Delta by Station",
        height=delta_height,
        yaxis_title="",
    )
    st.plotly_chart(delta_fig, use_container_width=True)

    st.subheader("Decision Driver Scatter Views")

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
            "region",
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
    price_util_fig.update_layout(title="Pricing vs Utilization")
    st.plotly_chart(price_util_fig, use_container_width=True)

    # Utilization vs Market Share
    market_position_fig = px.scatter(
        df,
        x="utilization_pct",
        y="market_share_pct",
        color="recommendation_score",
        color_continuous_scale=["#dc2626", "#94a3b8", "#1f9d55"],
        range_color=[-1, 1],
        hover_data=[
            "station",
            "region",
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
            "price_gap_pct": "Price Gap vs Competitor %",
        },
    )
    market_position_fig.add_vline(x=75, line_dash="dash", line_color="#94a3b8")
    market_position_fig.add_vline(x=90, line_dash="dash", line_color="#94a3b8")
    market_position_fig.add_hline(y=9, line_dash="dash", line_color="#94a3b8")
    market_position_fig.add_hline(y=15, line_dash="dash", line_color="#94a3b8")
    market_position_fig.update_layout(title="Market Share vs Utilization")
    st.plotly_chart(market_position_fig, use_container_width=True)

    # Utilization vs Daily Margin
    margin_util_fig = px.scatter(
        df,
        x="utilization_pct",
        y="daily_margin",
        color="recommendation_score",
        color_continuous_scale=["#dc2626", "#94a3b8", "#1f9d55"],
        range_color=[-1, 1],
        hover_data=[
            "station",
            "region",
            "segment",
            "recommendation",
            "confidence",
            "market_share_pct",
            "price_gap_pct",
            "pricing_signal",
            "recommended_fleet_delta",
            "reason_codes",
        ],
        labels={
            "utilization_pct": "Utilization %",
            "daily_margin": "Daily Margin",
            "recommendation_score": "Recommendation Signal",
            "price_gap_pct": "Price Gap vs Competitor %",
        },
    )
    margin_util_fig.add_vline(x=75, line_dash="dash", line_color="#94a3b8")
    margin_util_fig.add_vline(x=90, line_dash="dash", line_color="#94a3b8")
    margin_util_fig.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
    margin_util_fig.add_hline(y=15, line_dash="dash", line_color="#94a3b8")
    margin_util_fig.add_hline(y=40, line_dash="dash", line_color="#94a3b8")
    margin_util_fig.update_layout(title="Margin vs Utilization")
    st.plotly_chart(margin_util_fig, use_container_width=True)

def render_table(df: pd.DataFrame) -> None:
    columns = [
        "station",
        "region",
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

    bottom = st.columns(5)
    bottom[0].metric("Daily Margin", f"${row['daily_margin']:.2f}")
    bottom[1].metric("Price Gap", f"{row['price_gap_pct']:.1f}%")
    bottom[2].metric("Market Share", f"{row['market_share_pct']:.1f}%")
    bottom[3].metric("Target Fleet", f"{int(row['target_fleet_at_85_util']):,}")
    bottom[4].metric("Region", row["region"])

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

recommendations_df = ensure_region_column(st.session_state["recommendations"])
st.session_state["recommendations"] = recommendations_df
summary_data = st.session_state["summary"]
filtered_df = apply_filters(recommendations_df)

render_summary(filtered_df)

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
