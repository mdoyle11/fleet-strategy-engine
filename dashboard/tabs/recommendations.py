import pandas as pd
import streamlit as st


def render_table(df: pd.DataFrame) -> None:
    columns = [
        "station",
        "region",
        "segment",
        "fleet_size",
        "utilization_pct",
        "daily_roi",
        "estimated_daily_profit",
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
            "daily_roi": st.column_config.NumberColumn("daily_roi", format="percent"),
            "estimated_daily_profit": st.column_config.NumberColumn(
                "estimated_daily_profit",
                format="$%.2f",
            ),
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
