import pandas as pd
import streamlit as st


def build_row_choices(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.assign(label=lambda data: data["station"] + " / " + data["segment"])
        .sort_values("label")
        .reset_index(drop=True)
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
    bottom[0].metric("Daily ROI", f"{row['daily_roi']:.1%}")
    bottom[1].metric("Price Gap", f"{row['price_gap_pct']:.1f}%")
    bottom[2].metric("Market Share", f"{row['market_share_pct']:.1f}%")
    bottom[3].metric("Target Fleet", f"{int(row['target_fleet_at_85_util']):,}")
    bottom[4].metric("Region", row["region"])

    st.write(row["reasoning"])


