import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
stale_assistant_module = sys.modules.get("fleet_strategy_engine.assistant")
if stale_assistant_module is not None and not hasattr(stale_assistant_module, "__path__"):
    del sys.modules["fleet_strategy_engine.assistant"]

from dashboard.common import ensure_region_column
from dashboard.constants import (
    ARTIFACT_BASE_URI_ENV,
    PIPELINE_EXECUTION_MODE_ENV,
    PIPELINE_WAIT_SECONDS_ENV,
    RAW_UPLOAD_BASE_URI_ENV,
    SAMPLE_DATA_PATH,
)
from dashboard.shell import apply_filters, render_summary
from dashboard.tabs.assistant import render_assistant
from dashboard.tabs.charts import render_charts
from dashboard.tabs.downloads import render_downloads
from dashboard.tabs.drilldown import render_drilldown
from dashboard.tabs.recommendations import render_table
from dashboard.tabs.sensitivity import (
    render_sensitivity_metrics,
    render_sensitivity_rules,
)
from fleet_strategy_engine.pipeline import (
    INPUT_ARTIFACT,
    LOCAL_RUNS_URI,
    artifact_display_uri,
    artifact_uri,
    load_pipeline_outputs,
    pipeline_outputs_exist,
    run_artifact_uri,
    run_recommendation_file_pipeline,
    write_input_csv,
)
from fleet_strategy_engine.pipeline.validate import ValidationError


load_dotenv(override=True)

st.set_page_config(
    page_title="Fleet Strategy Engine",
    page_icon="",
    layout="wide",
)


def load_sample_data() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_DATA_PATH)


def artifact_base_uri() -> str:
    return os.environ.get(ARTIFACT_BASE_URI_ENV, LOCAL_RUNS_URI)


def raw_upload_base_uri() -> str:
    return os.environ.get(RAW_UPLOAD_BASE_URI_ENV, "outputs/raw/uploads")


def pipeline_execution_mode() -> str:
    return os.environ.get(PIPELINE_EXECUTION_MODE_ENV, "inline").lower()


def pipeline_wait_seconds() -> int:
    return int(os.environ.get(PIPELINE_WAIT_SECONDS_ENV, "30"))


def run_pipeline(input_df: pd.DataFrame, run_id: Optional[str] = None) -> None:
    run_id = run_id or uuid.uuid4().hex
    run_uri = run_artifact_uri(run_id, artifact_base_uri())

    if pipeline_execution_mode() == "lambda":
        raw_run_uri = run_artifact_uri(run_id, raw_upload_base_uri())
        write_input_csv(input_df, raw_run_uri)
        wait_for_pipeline_outputs(run_uri)
        st.session_state["raw_run_uri"] = artifact_display_uri(raw_run_uri)
    else:
        write_input_csv(input_df, run_uri)
        run_recommendation_file_pipeline(
            artifact_uri(run_uri, INPUT_ARTIFACT),
            run_uri,
        )

    artifact_recommendations, artifact_summary = load_pipeline_outputs(run_uri)

    st.session_state["input_df"] = input_df
    st.session_state["run_id"] = run_id
    st.session_state["run_uri"] = artifact_display_uri(run_uri)
    st.session_state["recommendations"] = artifact_recommendations
    st.session_state["summary"] = artifact_summary


def wait_for_pipeline_outputs(run_uri: str) -> None:
    deadline = time.time() + pipeline_wait_seconds()
    while time.time() < deadline:
        if pipeline_outputs_exist(run_uri):
            return
        time.sleep(1)
    raise TimeoutError(
        "Timed out waiting for Lambda to write recommendations.parquet and summary.json."
    )


st.title("Fleet Strategy Engine")

with st.sidebar:
    st.header("Run")
    uploaded = st.file_uploader("Upload fleet performance CSV", type=["csv"])
    use_sample = st.button("Reset to Sample Data", width="stretch")
    run_uploaded = st.button(
        "Run Recommendation",
        type="primary",
        width="stretch",
        disabled=uploaded is None,
    )

if "recommendations" not in st.session_state:
    try:
        run_pipeline(load_sample_data(), run_id="sample")
    except (ValidationError, FileNotFoundError) as exc:
        st.error(str(exc))
        st.stop()

if use_sample:
    try:
        run_pipeline(load_sample_data(), run_id="sample")
        st.success(f"Sample data processed: {st.session_state['run_uri']}")
    except (ValidationError, FileNotFoundError) as exc:
        st.error(str(exc))

if run_uploaded and uploaded is not None:
    try:
        run_pipeline(pd.read_csv(uploaded))
        st.success(f"Uploaded data processed: {st.session_state['run_uri']}")
    except ValidationError as exc:
        st.error(f"Validation failed: {exc}")
    except Exception as exc:
        st.error(f"Could not process file: {exc}")

recommendations_df = ensure_region_column(st.session_state["recommendations"])
st.session_state["recommendations"] = recommendations_df
summary_data = st.session_state["summary"]
filtered_df = apply_filters(recommendations_df)

render_summary(filtered_df)

tabs = st.tabs(
    [
        "Recommendations",
        "Charts",
        "Drilldown",
        "Sensitivity Analysis: Rules",
        "Sensitivity Analysis: Metrics",
        "Assistant",
        "Downloads",
    ]
)
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
    render_sensitivity_rules(filtered_df)
with tabs[4]:
    render_sensitivity_metrics(filtered_df)
with tabs[5]:
    if filtered_df.empty:
        st.info("No rows match the current filters.")
    else:
        render_assistant(filtered_df)
with tabs[6]:
    render_downloads(recommendations_df, summary_data)
