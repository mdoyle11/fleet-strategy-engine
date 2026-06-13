from pathlib import Path

import pandas as pd

from fleet_strategy_engine.pipeline import (
    RECOMMENDATIONS_ARTIFACT,
    SUMMARY_ARTIFACT,
    load_pipeline_outputs,
    local_run_dir,
    run_recommendation_file_pipeline,
    write_pipeline_outputs,
)


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
