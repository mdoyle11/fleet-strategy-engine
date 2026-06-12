import pandas as pd

from fleet_strategy_engine.pipeline import run_recommendation_pipeline
from fleet_strategy_engine.schemas import OUTPUT_COLUMNS


def test_pipeline_preserves_rows_and_adds_output_columns() -> None:
    input_df = pd.read_csv("tests/fixtures/valid_sample.csv")

    output_df, summary = run_recommendation_pipeline(input_df)

    assert len(output_df) == len(input_df)
    assert list(output_df.columns) == OUTPUT_COLUMNS
    assert summary["row_count"] == len(input_df)
    assert summary["station_count"] == input_df["station"].nunique()
    assert summary["segment_count"] == input_df["segment"].nunique()


def test_summary_counts_match_output() -> None:
    input_df = pd.read_csv("tests/fixtures/valid_sample.csv")

    output_df, summary = run_recommendation_pipeline(input_df)

    for action, count in summary["recommendation_counts"].items():
        assert count == int((output_df["recommendation"] == action).sum())
    assert summary["net_recommended_fleet_delta"] == int(output_df["recommended_fleet_delta"].sum())

