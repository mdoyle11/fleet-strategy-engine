import pandas as pd

from fleet_strategy_engine.config import DEFAULT_CONFIG, EngineConfig
from fleet_strategy_engine.engine.explain import add_explanations
from fleet_strategy_engine.engine.recommend import add_recommendations
from fleet_strategy_engine.pipeline.features import add_features
from fleet_strategy_engine.pipeline.summary import build_summary
from fleet_strategy_engine.pipeline.validate import validate_input
from fleet_strategy_engine.schemas import OUTPUT_COLUMNS


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

