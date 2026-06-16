import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.constants import COMPARISON_COLUMNS, METRIC_LABELS
from dashboard.formatting import comparison_frame
from dashboard.tabs.assistant import render_scenario_assistant
from dashboard.tabs.drilldown import build_row_choices
from fleet_strategy_engine.assistant.scenario_tools import (
    filtered_counts,
)
from fleet_strategy_engine.config import DEFAULT_CONFIG, EngineConfig
from fleet_strategy_engine.recommendation_context import reason_code_set
from fleet_strategy_engine.scenario_analysis import (
    add_fragility_columns,
    compare_rule_outputs,
    find_metric_flip as find_metric_flip_row,
    metric_bounds,
    metric_step,
    rerun_single_row,
    run_recommendations,
)
from fleet_strategy_engine.schemas import REQUIRED_COLUMNS


def scenario_config_from_sidebar() -> EngineConfig:
    st.caption(
        "These controls rerun the deterministic recommendation rules. They do not "
        "estimate causal demand response."
    )
    return EngineConfig(
        target_utilization=st.slider(
            "Target utilization",
            0.75,
            0.95,
            float(DEFAULT_CONFIG.target_utilization),
            0.01,
            format="%.2f",
        ),
        max_delta_pct=st.slider(
            "Max fleet delta per run",
            0.05,
            0.40,
            float(DEFAULT_CONFIG.max_delta_pct),
            0.01,
            format="%.2f",
        ),
        minimum_fleet_size=DEFAULT_CONFIG.minimum_fleet_size,
        weak_market_share_pct=st.slider(
            "Weak market share threshold",
            4.0,
            14.0,
            float(DEFAULT_CONFIG.weak_market_share_pct),
            0.5,
        ),
        strong_market_share_pct=st.slider(
            "Strong market share threshold",
            10.0,
            25.0,
            float(DEFAULT_CONFIG.strong_market_share_pct),
            0.5,
        ),
        underutilized_pct=st.slider(
            "Underutilized threshold",
            65.0,
            82.0,
            float(DEFAULT_CONFIG.underutilized_pct),
            0.5,
        ),
        high_utilization_pct=st.slider(
            "High utilization threshold",
            84.0,
            96.0,
            float(DEFAULT_CONFIG.high_utilization_pct),
            0.5,
        ),
        thin_roi_threshold=st.slider(
            "Thin ROI threshold",
            0.05,
            0.50,
            float(DEFAULT_CONFIG.thin_roi_threshold),
            0.01,
            format="%.2f",
        ),
        strong_roi_threshold=st.slider(
            "Strong ROI threshold",
            0.40,
            1.20,
            float(DEFAULT_CONFIG.strong_roi_threshold),
            0.01,
            format="%.2f",
        ),
    )


def compare_rule_scenario(baseline: pd.DataFrame, scenario: pd.DataFrame) -> pd.DataFrame:
    return compare_rule_outputs(baseline, scenario, include_reasoning=True)


def render_sensitivity_rules(df: pd.DataFrame) -> None:
    st.subheader("Sensitivity Analysis: Rules")
    st.caption(
        "Reruns the deterministic recommendation engine under changed planning "
        "thresholds. This tests decision robustness; it does not forecast demand."
    )
    if df.empty:
        st.info("No rows match the current filters.")
        return

    scenario_area, assistant_area = st.columns([2, 3])
    with scenario_area:
        config = scenario_config_from_sidebar()

    with assistant_area:
        render_scenario_assistant(df, "rules")

    scenario_df = run_recommendations(df, config)
    comparison = compare_rule_scenario(df, scenario_df)
    fragile = add_fragility_columns(df, DEFAULT_CONFIG)
    changed = comparison[comparison["scenario_change"] != "Stable"].copy()

    counts = filtered_counts(scenario_df)
    top = st.columns(5)
    top[0].metric("Changed Rows", f"{len(changed):,}")
    top[1].metric("BUY", f"{counts['BUY']:,}")
    top[2].metric("HOLD", f"{counts['HOLD']:,}")
    top[3].metric("REDUCE", f"{counts['REDUCE']:,}")
    top[4].metric(
        "Net Delta",
        f"{int(scenario_df['recommended_fleet_delta'].sum()):+}",
        delta=(
            int(scenario_df["recommended_fleet_delta"].sum())
            - int(df["recommended_fleet_delta"].sum())
        ),
    )

    if changed.empty:
        st.success("No recommendations changed under the selected rule assumptions.")
    else:
        change_counts = (
            changed["scenario_change"]
            .value_counts()
            .rename_axis("Change")
            .reset_index(name="Rows")
        )
        change_fig = px.bar(
            change_counts,
            x="Change",
            y="Rows",
            color="Change",
            color_discrete_sequence=px.colors.qualitative.Set2,
            title="Recommendation Changes by Scenario",
        )
        st.plotly_chart(change_fig, use_container_width=True)

    st.markdown("##### Fragile Recommendations")
    st.caption(
        "Rows are ranked by closeness to either an action-score boundary or a visible "
        "rule threshold such as utilization, ROI, market share, or pricing."
    )
    fragile_view = fragile.sort_values(
        ["score_margin_to_action_change", "nearest_threshold_distance"]
    ).head(15)
    st.dataframe(
        fragile_view[
            [
                "station",
                "region",
                "segment",
                "recommendation",
                "recommendation_score",
                "confidence",
                "score_margin_to_action_change",
                "nearest_rule_threshold",
                "nearest_threshold_distance",
                "recommended_fleet_delta",
                "reason_codes",
            ]
        ],
        width="stretch",
        hide_index=True,
        column_config={
            "recommendation_score": st.column_config.ProgressColumn(
                "recommendation_score",
                min_value=-1.0,
                max_value=1.0,
                format="%.2f",
            ),
            "score_margin_to_action_change": st.column_config.NumberColumn(
                "score margin to action change",
                format="%.2f",
            ),
            "nearest_threshold_distance": st.column_config.NumberColumn(
                "nearest threshold distance",
                format="%.2f pts",
            ),
            "recommended_fleet_delta": st.column_config.NumberColumn(
                "recommended_fleet_delta",
                format="%+d",
            ),
        },
    )

    st.markdown("##### Scenario Changes")
    if changed.empty:
        st.info("Adjust the rule controls to see which rows flip under alternate assumptions.")
    else:
        changed_view = changed.sort_values(
            ["absolute_score_change", "station", "segment"],
            ascending=[False, True, True],
        )
        st.dataframe(
            changed_view[
                [
                    "station",
                    "region",
                    "segment",
                    "recommendation",
                    "scenario_recommendation",
                    "recommendation_score",
                    "scenario_recommendation_score",
                    "score_change",
                    "recommended_fleet_delta",
                    "scenario_recommended_fleet_delta",
                    "delta_change",
                    "scenario_change",
                ]
            ],
            width="stretch",
            hide_index=True,
            column_config={
                "recommendation_score": st.column_config.NumberColumn(
                    "baseline score",
                    format="%.2f",
                ),
                "scenario_recommendation_score": st.column_config.NumberColumn(
                    "scenario score",
                    format="%.2f",
                ),
                "score_change": st.column_config.NumberColumn(
                    "score change",
                    format="%+.2f",
                ),
                "recommended_fleet_delta": st.column_config.NumberColumn(
                    "baseline delta",
                    format="%+d",
                ),
                "scenario_recommended_fleet_delta": st.column_config.NumberColumn(
                    "scenario delta",
                    format="%+d",
                ),
                "delta_change": st.column_config.NumberColumn(
                    "delta change",
                    format="%+d",
                ),
            },
        )


def find_metric_flip(row: pd.Series, column: str) -> dict[str, object]:
    return find_metric_flip_row(row, column, METRIC_LABELS[column])


def render_sensitivity_metrics(df: pd.DataFrame) -> None:
    st.subheader("Sensitivity Analysis: Metrics")
    st.caption(
        "Edit one opportunity's observed inputs and rerun the deterministic engine. "
        "Changing price, cost, utilization, or market share here does not imply a "
        "causal relationship among those metrics."
    )
    choices = build_row_choices(df)
    if choices.empty:
        st.info("No rows match the current filters.")
        return

    scenario_area, assistant_area = st.columns([2, 3])
    with scenario_area:
        selected = st.selectbox(
            "Select opportunity",
            choices["label"],
            key="metric_sensitivity_row",
        )
        row = choices.loc[choices["label"] == selected].iloc[0]

        updates: dict[str, float] = {}
        st.markdown("##### What-If Inputs")
        for column in REQUIRED_COLUMNS:
            if column in {"station", "segment"}:
                continue
            current_value = float(row[column])
            lower, upper = metric_bounds(column, current_value)
            step = metric_step(column)
            if column == "fleet_size":
                updates[column] = st.number_input(
                    METRIC_LABELS[column],
                    min_value=int(lower),
                    max_value=int(upper),
                    value=int(round(current_value)),
                    step=int(step),
                )
            else:
                updates[column] = st.number_input(
                    METRIC_LABELS[column],
                    min_value=float(lower),
                    max_value=float(upper),
                    value=float(current_value),
                    step=float(step),
                    format="%.2f",
                )
    with assistant_area:
        render_scenario_assistant(df, "metrics")

    scenario_row = rerun_single_row(row, updates)
    added_codes = reason_code_set(scenario_row["reason_codes"]) - reason_code_set(
        row["reason_codes"]
    )
    removed_codes = reason_code_set(row["reason_codes"]) - reason_code_set(
        scenario_row["reason_codes"]
    )

    metrics = st.columns(5)
    metrics[0].metric(
        "Recommendation",
        scenario_row["recommendation"],
        delta=(
            "changed"
            if scenario_row["recommendation"] != row["recommendation"]
            else "stable"
        ),
    )
    metrics[1].metric(
        "Signal",
        f"{scenario_row['recommendation_score']:+.2f}",
        delta=f"{scenario_row['recommendation_score'] - row['recommendation_score']:+.2f}",
    )
    metrics[2].metric("Confidence", scenario_row["confidence"])
    metrics[3].metric(
        "Fleet Delta",
        f"{int(scenario_row['recommended_fleet_delta']):+}",
        delta=int(
            scenario_row["recommended_fleet_delta"]
            - row["recommended_fleet_delta"]
        ),
    )
    metrics[4].metric(
        "Daily ROI",
        f"{scenario_row['daily_roi']:.1%}",
        delta=f"{scenario_row['daily_roi'] - row['daily_roi']:+.1%}",
    )

    st.write(scenario_row["reasoning"])
    reason_cols = st.columns(2)
    reason_cols[0].write(
        "Added reason codes: " + (", ".join(sorted(added_codes)) or "none")
    )
    reason_cols[1].write(
        "Removed reason codes: " + (", ".join(sorted(removed_codes)) or "none")
    )

    st.markdown("##### Current vs What-If")
    st.dataframe(
        comparison_frame(row, scenario_row, COMPARISON_COLUMNS),
        width="stretch",
        hide_index=True,
    )

    st.markdown("##### Distance to Flip")
    st.caption(
        "Each row changes one metric at a time from the current baseline and reports "
        "the closest tested value that changes the recommendation."
    )
    flip_rows = pd.DataFrame(
        [
            find_metric_flip(row, column)
            for column in REQUIRED_COLUMNS
            if column not in {"station", "segment"}
        ]
    )
    st.dataframe(
        flip_rows,
        width="stretch",
        hide_index=True,
        column_config={
            "current_value": st.column_config.NumberColumn("current value", format="%.2f"),
            "flip_value": st.column_config.NumberColumn("flip value", format="%.2f"),
            "change_needed": st.column_config.NumberColumn(
                "change needed",
                format="%+.2f",
            ),
            "new_score": st.column_config.NumberColumn("new score", format="%+.2f"),
        },
    )
