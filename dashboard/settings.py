import os

from fleet_strategy_engine.pipeline import LOCAL_RUNS_URI

from dashboard.constants import (
    ARTIFACT_BASE_URI_ENV,
    PIPELINE_EXECUTION_MODE_ENV,
    PIPELINE_WAIT_SECONDS_ENV,
    RAW_UPLOAD_BASE_URI_ENV,
)


def artifact_base_uri() -> str:
    return os.environ.get(ARTIFACT_BASE_URI_ENV, LOCAL_RUNS_URI)


def raw_upload_base_uri() -> str:
    return os.environ.get(RAW_UPLOAD_BASE_URI_ENV, "outputs/raw/uploads")


def pipeline_execution_mode() -> str:
    return os.environ.get(PIPELINE_EXECUTION_MODE_ENV, "inline").lower()


def pipeline_wait_seconds() -> int:
    return int(os.environ.get(PIPELINE_WAIT_SECONDS_ENV, "30"))
