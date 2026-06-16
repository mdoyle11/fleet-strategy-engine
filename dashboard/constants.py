from pathlib import Path

from fleet_strategy_engine.geography import STATION_REGION_MAP


SAMPLE_DATA_PATH = Path("data/sample_data.csv")
ARTIFACT_BASE_URI_ENV = "FLEET_ARTIFACT_BASE_URI"
PIPELINE_EXECUTION_MODE_ENV = "FLEET_PIPELINE_EXECUTION_MODE"
RAW_UPLOAD_BASE_URI_ENV = "FLEET_RAW_UPLOAD_BASE_URI"
PIPELINE_WAIT_SECONDS_ENV = "FLEET_PIPELINE_WAIT_SECONDS"
ACTION_ORDER = ["BUY", "HOLD", "REDUCE"]
REGION_ORDER = ["Northeast", "South", "Midwest", "West", "Unknown"]
SEGMENT_ORDER = ["Economy", "SUV", "Premium", "Minivan", "Truck"]
ACTION_COLORS = {
    "BUY": "#1f9d55",
    "HOLD": "#64748b",
    "REDUCE": "#dc2626",
}
METRIC_LABELS = {
    "fleet_size": "Fleet Size",
    "utilization_pct": "Utilization %",
    "avg_daily_rate": "Avg Daily Rate",
    "avg_daily_fleet_cost": "Avg Daily Fleet Cost",
    "avg_daily_operating_cost": "Avg Daily Operating Cost",
    "competitor_rate": "Competitor Rate",
    "market_share_pct": "Market Share %",
}
COMPARISON_COLUMNS = [
    "fleet_size",
    "utilization_pct",
    "avg_daily_rate",
    "avg_daily_fleet_cost",
    "avg_daily_operating_cost",
    "competitor_rate",
    "market_share_pct",
    "daily_margin",
    "daily_roi",
    "estimated_daily_profit",
    "price_gap_pct",
    "recommendation",
    "recommendation_score",
    "confidence",
    "recommended_fleet_delta",
]
