import json
from pathlib import Path

import pandas as pd

from fleet_strategy_engine.config import DEFAULT_CONFIG, EngineConfig
from fleet_strategy_engine.engine.explain import add_explanations
from fleet_strategy_engine.engine.recommend import add_recommendations
from fleet_strategy_engine.pipeline.features import add_features
from fleet_strategy_engine.pipeline.summary import build_summary
from fleet_strategy_engine.pipeline.validate import validate_input
from fleet_strategy_engine.schemas import OUTPUT_COLUMNS


LOCAL_RUNS_DIR = Path("outputs/runs")
INPUT_ARTIFACT = "input.csv"
RECOMMENDATIONS_ARTIFACT = "recommendations.parquet"
SUMMARY_ARTIFACT = "summary.json"


def run_recommendation_pipeline(
    input_df: pd.DataFrame,
    config: EngineConfig = DEFAULT_CONFIG,
) -> tuple[pd.DataFrame, dict]:
    validate_input(input_df)
    featured = add_features(input_df, config)
    recommended = add_recommendations(featured, config)
    explained = add_explanations(recommended)
    summary = build_summary(explained)
    return explained[OUTPUT_COLUMNS], summary


def local_run_dir(run_id: str, base_dir: Path = LOCAL_RUNS_DIR) -> Path:
    return base_dir / run_id


def run_recommendation_file_pipeline(
    input_path: Path,
    output_dir: Path,
    config: EngineConfig = DEFAULT_CONFIG,
) -> tuple[pd.DataFrame, dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    input_df = pd.read_csv(input_path)
    recommendations, summary = run_recommendation_pipeline(input_df, config)
    write_pipeline_outputs(recommendations, summary, output_dir)
    return recommendations, summary


def write_pipeline_outputs(
    recommendations: pd.DataFrame,
    summary: dict,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    recommendations.to_parquet(output_dir / RECOMMENDATIONS_ARTIFACT, index=False)
    (output_dir / SUMMARY_ARTIFACT).write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )


def load_pipeline_outputs(output_dir: Path) -> tuple[pd.DataFrame, dict]:
    recommendations = pd.read_parquet(output_dir / RECOMMENDATIONS_ARTIFACT)
    summary = json.loads((output_dir / SUMMARY_ARTIFACT).read_text(encoding="utf-8"))
    return recommendations, summary
