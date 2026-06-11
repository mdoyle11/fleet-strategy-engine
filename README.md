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
  --output outputs/recommendations.csv \
  --summary-output outputs/summary.json
```

The CLI also writes `outputs/recommendations.json`.

## Run Tests

```bash
uv run pytest
```

## Project Layout

- `src/fleet_strategy_engine/pipeline/`: validation, feature engineering, orchestration, and summaries.
- `src/fleet_strategy_engine/engine/`: deterministic recommendation scoring and explanations.
- `main.py`: thin CLI wrapper around the reusable pipeline.
- `dashboard/`: placeholder for the later Streamlit app.

## Current Scope

This phase includes only the local data pipeline and recommendation engine. Dashboard, AI interpretation, and AWS deployment will be added in later phases.

