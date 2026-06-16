import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.tabs.sensitivity import comparison_frame


def test_comparison_frame_formats_mixed_values_as_text() -> None:
    current = pd.Series(
        {
            "fleet_size": 10,
            "utilization_pct": 80.0,
            "avg_daily_rate": 100.0,
            "avg_daily_fleet_cost": 35.0,
            "avg_daily_operating_cost": 15.0,
            "competitor_rate": 110.0,
            "market_share_pct": 12.0,
            "daily_margin": 50.0,
            "daily_roi": 1.0,
            "estimated_daily_profit": 450.0,
            "price_gap_pct": -9.1,
            "recommendation": "HOLD",
            "recommendation_score": 0.0,
            "confidence": "high",
            "recommended_fleet_delta": 0,
        }
    )
    scenario = current.copy()
    scenario["recommendation"] = "REDUCE"
    scenario["daily_roi"] = 0.5
    scenario["estimated_daily_profit"] = 200.0

    result = comparison_frame(current, scenario)

    assert result["Current"].map(type).eq(str).all()
    assert result["What-If"].map(type).eq(str).all()
    assert result["Change"].map(type).eq(str).all()
    assert result.loc[result["Metric"] == "recommendation", "Change"].iloc[0] == "changed"
    assert result.loc[result["Metric"] == "daily_roi", "Change"].iloc[0] == "-50.0%"
