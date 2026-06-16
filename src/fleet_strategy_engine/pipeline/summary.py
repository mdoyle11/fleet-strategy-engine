from datetime import datetime, timezone
from typing import Any

import pandas as pd

from fleet_strategy_engine.recommendation_context import recommendation_counts


def build_summary(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "row_count": int(len(df)),
        "station_count": int(df["station"].nunique()),
        "segment_count": int(df["segment"].nunique()),
        "recommendation_counts": recommendation_counts(df),
        "net_recommended_fleet_delta": int(df["recommended_fleet_delta"].sum()),
        "avg_utilization_pct": round(float(df["utilization_pct"].mean()), 2),
        "avg_daily_margin": round(float(df["daily_margin"].mean()), 2),
        "avg_daily_roi": round(float(df["daily_roi"].mean()), 4),
        "total_estimated_daily_profit": round(float(df["estimated_daily_profit"].sum()), 2),
        "high_risk_count": int(
            ((df["recommendation"] == "REDUCE") | (df["daily_roi"] <= 0)).sum()
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
