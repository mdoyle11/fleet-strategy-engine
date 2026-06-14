# Fleet Strategy Engine

A local-first recommendation engine for fleet planning decisions. The project reads station and vehicle-segment performance data, validates the batch, computes planning features, and returns deterministic `BUY`, `HOLD`, or `REDUCE` recommendations with reason codes and planner-facing explanations.

The engine is intentionally rule based and auditable. It does not use supervised machine learning because the case data does not include historical decision labels or outcome feedback.

## Setup

```bash
uv sync
```

## Run The Pipeline

```bash
uv run python main.py \
  --input data/sample_data.csv \
  --output outputs/recommendations.parquet \
  --csv-output outputs/recommendations.csv \
  --summary-output outputs/summary.json
```

The Parquet file is the canonical row-level output for dashboard and future AWS processing. The CSV output is optional and intended for analyst download/export.

## Run Tests

```bash
uv run pytest
```

## Artifact Storage

The pipeline writes row-level recommendations to Parquet and summary metrics to JSON. The dashboard uses the same artifact path locally and in AWS:

```text
{artifact_base_uri}/{run_id}/input.csv
{artifact_base_uri}/{run_id}/recommendations.parquet
{artifact_base_uri}/{run_id}/summary.json
```

By default, `artifact_base_uri` is `outputs/runs`. To point the dashboard at S3, set:

```bash
export FLEET_ARTIFACT_BASE_URI="s3://your-bucket/processed/runs"
```

## Project Layout

- `src/fleet_strategy_engine/pipeline/`: validation, feature engineering, orchestration, and summaries.
- `src/fleet_strategy_engine/engine/`: deterministic recommendation scoring and explanations.
- `main.py`: thin CLI wrapper around the reusable pipeline.
- `dashboard/`: Streamlit dashboard that reads processed Parquet output and summary artifacts.
- `infra/terraform/`: initial AWS infrastructure for the artifact bucket.
- `Dockerfile.lambda`: container image entrypoint for Lambda-backed pipeline execution.

## Current Scope

The local MVP includes the deterministic data pipeline, Streamlit dashboard, and optional LangGraph/Gemini assistant. The dashboard now uses a local-or-S3 artifact URI so the read/write path can move to S3 without changing recommendation logic.
