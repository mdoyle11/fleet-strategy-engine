# Dashboard

Run the local dashboard with:

```bash
uv run streamlit run dashboard/app.py
```

The dashboard imports the reusable pipeline from `fleet_strategy_engine` and does not duplicate recommendation logic.

## Artifact Storage

On first load, the dashboard processes the sample data through the same artifact path used for uploads. When you reset to sample data or upload a CSV, the dashboard writes an input artifact, runs the pipeline, and reloads dashboard state from the processed outputs:

```text
{artifact_base_uri}/{run_id}/input.csv
{artifact_base_uri}/{run_id}/recommendations.parquet
{artifact_base_uri}/{run_id}/summary.json
```

By default, `artifact_base_uri` is `outputs/runs`. To use S3, set:

```bash
export FLEET_ARTIFACT_BASE_URI="s3://your-bucket/processed/runs"
```

The initial Terraform in `infra/terraform` creates the artifact bucket and outputs a matching `FLEET_ARTIFACT_BASE_URI` value. This mirrors the planned AWS flow where the dashboard reads processed Parquet and summary artifacts from S3.

## Lambda Execution Mode

By default, the dashboard runs the pipeline inline after writing the input artifact. To move execution to the S3-triggered Lambda path, set:

```bash
export FLEET_PIPELINE_EXECUTION_MODE="lambda"
export FLEET_ARTIFACT_BASE_URI="$(terraform -chdir=infra/terraform output -raw dashboard_artifact_base_uri)"
export FLEET_RAW_UPLOAD_BASE_URI="$(terraform -chdir=infra/terraform output -raw dashboard_raw_upload_base_uri)"
```

In this mode, the dashboard uploads:

```text
s3://bucket/raw/uploads/{run_id}/input.csv
```

Then it waits for Lambda to write:

```text
s3://bucket/processed/runs/{run_id}/recommendations.parquet
s3://bucket/processed/runs/{run_id}/summary.json
```

## Assistant

The Assistant tab is optional. It elaborates on the deterministic recommendation output using the visible filtered rows, metrics, recommendation scores, confidence, and reason-code reference.

The LLM layer lives in `src/fleet_strategy_engine/assistant.py`, separate from the Streamlit app. It uses LangGraph to orchestrate a compact answer-validation loop:

```text
generate answer -> validate -> repair/retry if needed -> final answer or deterministic fallback
```

If the answer cannot pass validation after the configured retries, the dashboard shows a deterministic summary from the recommendation output instead of exposing the invalid LLM answer.

Set a Gemini API key before launching Streamlit:

```bash
export GOOGLE_API_KEY="..."
```

Or put it in a root-level `.env` file:

```bash
GOOGLE_API_KEY="..."
```

Optionally override the default model:

```bash
export GEMINI_MODEL="gemini-3.5-flash"
```

The `.env` file is ignored by git.
