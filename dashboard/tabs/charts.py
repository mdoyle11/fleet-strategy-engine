import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.constants import ACTION_COLORS, SEGMENT_ORDER
from fleet_strategy_engine.config import DEFAULT_CONFIG


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


def profitability_ranking_frame(df: pd.DataFrame, limit: int = 12) -> pd.DataFrame:
    ranked = df.copy()
    if ranked.empty:
        return ranked

    ranked["station_segment"] = ranked["station"] + " / " + ranked["segment"]
    return ranked.sort_values(
        ["estimated_daily_profit", "recommended_fleet_delta", "utilization_pct"],
        ascending=[True, True, True],
    ).head(limit)


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
                    "daily_roi",
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

    profitability_ranking = profitability_ranking_frame(df)
    if profitability_ranking.empty:
        st.info("No profitability opportunities match the current filters.")
    else:
        profitability_fig = px.bar(
            profitability_ranking,
            x="estimated_daily_profit",
            y="station_segment",
            orientation="h",
            color="recommendation_score",
            color_continuous_scale=["#dc2626", "#94a3b8", "#1f9d55"],
            range_color=[-1, 1],
            hover_data=[
                "station",
                "region",
                "segment",
                "recommendation",
                "confidence",
                "fleet_size",
                "utilization_pct",
                "daily_roi",
                "recommended_fleet_delta",
                "reason_codes",
            ],
            labels={
                "station_segment": "Station / Segment",
                "estimated_daily_profit": "Estimated Daily Profit",
                "recommendation_score": "Recommendation Signal",
            },
        )
        profitability_fig.add_vline(x=0, line_dash="dot", line_color="#94a3b8")
        profitability_fig.update_layout(
            title="Lowest Profitability Opportunities",
            yaxis={
                "categoryorder": "array",
                "categoryarray": profitability_ranking["station_segment"].iloc[::-1].tolist(),
                "title": "",
            },
        )
        st.plotly_chart(profitability_fig, use_container_width=True)

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
            "daily_roi",
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
    price_util_fig.add_hline(
        y=DEFAULT_CONFIG.underutilized_pct,
        line_dash="dash",
        line_color="#94a3b8",
    )
    price_util_fig.add_hline(
        y=DEFAULT_CONFIG.high_utilization_pct,
        line_dash="dash",
        line_color="#94a3b8",
    )
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
            "daily_roi",
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
    market_position_fig.add_vline(
        x=DEFAULT_CONFIG.underutilized_pct,
        line_dash="dash",
        line_color="#94a3b8",
    )
    market_position_fig.add_vline(
        x=DEFAULT_CONFIG.high_utilization_pct,
        line_dash="dash",
        line_color="#94a3b8",
    )
    market_position_fig.add_hline(
        y=DEFAULT_CONFIG.weak_market_share_pct,
        line_dash="dash",
        line_color="#94a3b8",
    )
    market_position_fig.add_hline(
        y=DEFAULT_CONFIG.strong_market_share_pct,
        line_dash="dash",
        line_color="#94a3b8",
    )
    market_position_fig.update_layout(title="Market Share vs Utilization")
    st.plotly_chart(market_position_fig, use_container_width=True)

    # Utilization vs Daily ROI
    roi_util_fig = px.scatter(
        df,
        x="utilization_pct",
        y="daily_roi",
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
            "daily_roi": "Daily ROI",
            "recommendation_score": "Recommendation Signal",
            "price_gap_pct": "Price Gap vs Competitor %",
        },
    )
    roi_util_fig.add_vline(
        x=DEFAULT_CONFIG.underutilized_pct,
        line_dash="dash",
        line_color="#94a3b8",
    )
    roi_util_fig.add_vline(
        x=DEFAULT_CONFIG.high_utilization_pct,
        line_dash="dash",
        line_color="#94a3b8",
    )
    roi_util_fig.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
    roi_util_fig.add_hline(
        y=DEFAULT_CONFIG.thin_roi_threshold,
        line_dash="dash",
        line_color="#94a3b8",
    )
    roi_util_fig.add_hline(
        y=DEFAULT_CONFIG.strong_roi_threshold,
        line_dash="dash",
        line_color="#94a3b8",
    )
    roi_util_fig.update_layout(title="ROI vs Utilization")
    st.plotly_chart(roi_util_fig, use_container_width=True)

    # ROI vs Price Gap
    roi_price_fig = px.scatter(
        df,
        x="price_gap_pct",
        y="daily_roi",
        color="recommendation_score",
        color_continuous_scale=["#dc2626", "#94a3b8", "#1f9d55"],
        range_color=[-1, 1],
        hover_data=[
            "station",
            "region",
            "segment",
            "recommendation",
            "confidence",
            "utilization_pct",
            "market_share_pct",
            "pricing_signal",
            "recommended_fleet_delta",
            "reason_codes",
        ],
        labels={
            "price_gap_pct": "Price Gap vs Competitor %",
            "daily_roi": "Daily ROI",
            "recommendation_score": "Recommendation Signal",
            "utilization_pct": "Utilization %",
            "market_share_pct": "Market Share %",
        },
    )
    roi_price_fig.add_vline(x=-10, line_dash="dash", line_color="#94a3b8")
    roi_price_fig.add_vline(x=0, line_dash="dot", line_color="#94a3b8")
    roi_price_fig.add_vline(x=10, line_dash="dash", line_color="#94a3b8")
    roi_price_fig.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
    roi_price_fig.add_hline(
        y=DEFAULT_CONFIG.thin_roi_threshold,
        line_dash="dash",
        line_color="#94a3b8",
    )
    roi_price_fig.add_hline(
        y=DEFAULT_CONFIG.strong_roi_threshold,
        line_dash="dash",
        line_color="#94a3b8",
    )
    roi_price_fig.update_layout(title="ROI vs Price Gap")
    st.plotly_chart(roi_price_fig, use_container_width=True)

    # Market Share vs Price Gap
    market_price_fig = px.scatter(
        df,
        x="price_gap_pct",
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
            "utilization_pct",
            "daily_roi",
            "pricing_signal",
            "recommended_fleet_delta",
            "reason_codes",
        ],
        labels={
            "price_gap_pct": "Price Gap vs Competitor %",
            "market_share_pct": "Market Share %",
            "recommendation_score": "Recommendation Signal",
            "utilization_pct": "Utilization %",
            "daily_roi": "Daily ROI",
        },
    )
    market_price_fig.add_vline(x=-10, line_dash="dash", line_color="#94a3b8")
    market_price_fig.add_vline(x=0, line_dash="dot", line_color="#94a3b8")
    market_price_fig.add_vline(x=10, line_dash="dash", line_color="#94a3b8")
    market_price_fig.add_hline(
        y=DEFAULT_CONFIG.weak_market_share_pct,
        line_dash="dash",
        line_color="#94a3b8",
    )
    market_price_fig.add_hline(
        y=DEFAULT_CONFIG.strong_market_share_pct,
        line_dash="dash",
        line_color="#94a3b8",
    )
    market_price_fig.update_layout(title="Market Share vs Price Gap")
    st.plotly_chart(market_price_fig, use_container_width=True)
