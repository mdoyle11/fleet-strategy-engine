import pandas as pd

from fleet_strategy_engine.pipeline import run_recommendation_pipeline
from fleet_strategy_engine.schemas import OUTPUT_COLUMNS


def test_pipeline_preserves_rows_and_adds_outputs() -> None:
    input_df = pd.read_csv("tests/fixtures/valid_sample.csv")

    recommendations, summary = run_recommendation_pipeline(input_df)

    assert len(recommendations) == len(input_df)
    assert list(recommendations.columns) == OUTPUT_COLUMNS
    assert summary["row_count"] == len(input_df)
    assert summary["station_count"] == 3
    assert sum(summary["recommendation_counts"].values()) == len(input_df)

