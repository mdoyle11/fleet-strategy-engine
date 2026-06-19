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
    SAMPLE_DATA_PATH,
)
from dashboard.settings import (
    artifact_base_uri,
    pipeline_execution_mode,
    pipeline_wait_seconds,
    raw_upload_base_uri,
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
    artifact_uri,
    load_latest_run_uri,
    load_pipeline_outputs,
    pipeline_outputs_exist,
    run_artifact_uri,
    run_recommendation_file_pipeline,
    write_input_csv,
    write_latest_run_pointer,
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


def load_run(run_uri: str, input_df: Optional[pd.DataFrame] = None) -> None:
    recommendations, summary = load_pipeline_outputs(run_uri)
    run_id = str(run_uri).rstrip("/").rsplit("/", 1)[-1]

    if input_df is not None:
        st.session_state["input_df"] = input_df
    else:
        st.session_state.pop("input_df", None)
    st.session_state["run_id"] = run_id
    st.session_state["run_uri"] = str(run_uri)
    st.session_state["recommendations"] = recommendations
    st.session_state["summary"] = summary


def load_latest_run() -> bool:
    latest_run_uri = load_latest_run_uri(artifact_base_uri())
    if latest_run_uri is None or not pipeline_outputs_exist(latest_run_uri):
        return False
    load_run(latest_run_uri)
    return True


def run_pipeline(input_df: pd.DataFrame, run_id: Optional[str] = None) -> None:
    run_id = run_id or uuid.uuid4().hex
    run_uri = run_artifact_uri(run_id, artifact_base_uri())

    if pipeline_execution_mode() == "lambda":
        raw_run_uri = run_artifact_uri(run_id, raw_upload_base_uri())
        write_input_csv(input_df, raw_run_uri)
        wait_for_pipeline_outputs(run_uri)
        st.session_state["raw_run_uri"] = str(raw_run_uri)
    else:
        write_input_csv(input_df, run_uri)
        run_recommendation_file_pipeline(
            artifact_uri(run_uri, INPUT_ARTIFACT),
            run_uri,
        )
        if run_id != "sample":
            write_latest_run_pointer(artifact_base_uri(), run_id)

    load_run(run_uri, input_df)


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
        if not load_latest_run():
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
