from pathlib import Path

import pandas as pd

from fleet_strategy_engine.pipeline import (
    INPUT_ARTIFACT,
    RECOMMENDATIONS_ARTIFACT,
    SUMMARY_ARTIFACT,
    load_pipeline_outputs,
    local_run_dir,
    pipeline_outputs_exist,
    run_artifact_uri,
    run_recommendation_file_pipeline,
    write_input_csv,
    write_pipeline_outputs,
)
from fleet_strategy_engine.pipeline.io import S3ArtifactStore


def test_local_run_artifacts_round_trip(tmp_path: Path) -> None:
    recommendations = pd.DataFrame(
        [
            {
                "station": "JFK",
                "segment": "SUV",
                "recommendation": "BUY",
                "recommendation_score": 0.83,
            }
        ]
    )
    summary = {"row_count": 1, "recommendation_counts": {"BUY": 1}}

    run_dir = local_run_dir("test-run", tmp_path)
    write_pipeline_outputs(
        recommendations,
        summary,
        run_dir,
    )
    loaded_recommendations, loaded_summary = load_pipeline_outputs(run_dir)

    assert (run_dir / RECOMMENDATIONS_ARTIFACT).exists()
    assert (run_dir / SUMMARY_ARTIFACT).exists()
    assert list(loaded_recommendations.columns) == list(recommendations.columns)
    assert loaded_recommendations.loc[0, "station"] == "JFK"
    assert loaded_summary == summary
    assert pipeline_outputs_exist(run_dir)


def test_run_artifact_uri_supports_local_and_s3_roots(tmp_path: Path) -> None:
    assert run_artifact_uri("abc123", tmp_path) == str(tmp_path / "abc123")
    assert (
        run_artifact_uri("abc123", "s3://fleet-strategy/processed/runs")
        == "s3://fleet-strategy/processed/runs/abc123"
    )


def test_s3_artifact_store_parses_bucket_and_prefix() -> None:
    store = S3ArtifactStore.from_uri("s3://fleet-strategy/processed/runs/abc123")

    assert store.bucket == "fleet-strategy"
    assert store.prefix == "processed/runs/abc123"
    assert store._key(RECOMMENDATIONS_ARTIFACT) == (
        "processed/runs/abc123/recommendations.parquet"
    )


def test_write_input_csv_uses_artifact_backend(tmp_path: Path) -> None:
    run_dir = local_run_dir("test-input", tmp_path)
    input_df = pd.DataFrame(
        [
            {
                "station": "JFK",
                "segment": "SUV",
                "fleet_size": 10,
            }
        ]
    )

    write_input_csv(input_df, run_dir)

    loaded = pd.read_csv(run_dir / INPUT_ARTIFACT)
    assert loaded.loc[0, "station"] == "JFK"


def test_file_pipeline_writes_processed_artifacts(tmp_path: Path) -> None:
    input_path = tmp_path / "input.csv"
    output_dir = tmp_path / "run-output"
    pd.DataFrame(
        [
            {
                "station": "JFK",
                "segment": "SUV",
                "fleet_size": 10,
                "utilization_pct": 90,
                "avg_daily_rate": 120,
                "avg_daily_fleet_cost": 35,
                "avg_daily_operating_cost": 15,
                "competitor_rate": 130,
                "market_share_pct": 18,
            }
        ]
    ).to_csv(input_path, index=False)

    recommendations, summary = run_recommendation_file_pipeline(input_path, output_dir)
    loaded_recommendations, loaded_summary = load_pipeline_outputs(output_dir)

    assert (output_dir / RECOMMENDATIONS_ARTIFACT).exists()
    assert (output_dir / SUMMARY_ARTIFACT).exists()
    assert len(recommendations) == 1
    assert len(loaded_recommendations) == 1
    assert loaded_summary == summary
