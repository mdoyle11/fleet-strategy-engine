import pandas as pd
import pytest

from fleet_strategy_engine.assistant.scenario_tools import (
    ScenarioToolError,
    config_with_updates,
    metric_scenario,
    rule_scenario,
)


def sample_input() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "station": "JFK",
                "segment": "SUV",
                "fleet_size": 50,
                "utilization_pct": 92,
                "avg_daily_rate": 120,
                "avg_daily_fleet_cost": 40,
                "avg_daily_operating_cost": 15,
                "competitor_rate": 125,
                "market_share_pct": 16,
            },
            {
                "station": "ORD",
                "segment": "Economy",
                "fleet_size": 80,
                "utilization_pct": 68,
                "avg_daily_rate": 45,
                "avg_daily_fleet_cost": 25,
                "avg_daily_operating_cost": 12,
                "competitor_rate": 50,
                "market_share_pct": 7,
            },
        ]
    )


def test_config_with_updates_validates_rule_fields() -> None:
    config = config_with_updates({"high_utilization_pct": 88})

    assert config.high_utilization_pct == 88

    with pytest.raises(ScenarioToolError, match="Unsupported scenario fields"):
        config_with_updates({"unknown": 1})


def test_rule_scenario_returns_changed_rows_and_fragile_rows() -> None:
    result = rule_scenario(sample_input(), {"high_utilization_pct": 94})

    assert result["tool"] == "run_rule_scenario"
    assert result["scenario_counts"]["BUY"] <= result["baseline_counts"]["BUY"]
    assert "changed_rows" in result
    assert result["fragile_rows"]


def test_metric_scenario_reruns_single_opportunity() -> None:
    result = metric_scenario(
        sample_input(),
        "JFK",
        "SUV",
        {"avg_daily_rate": 50},
    )

    assert result["tool"] == "run_metric_scenario"
    assert result["station"] == "JFK"
    assert result["segment"] == "SUV"
    assert result["current"]["recommendation"] == "BUY"
    assert result["scenario"]["daily_roi"] < result["current"]["daily_roi"]


def test_metric_scenario_rejects_missing_opportunity() -> None:
    with pytest.raises(ScenarioToolError, match="No opportunity found"):
        metric_scenario(sample_input(), "ATL", "SUV", {"utilization_pct": 80})
