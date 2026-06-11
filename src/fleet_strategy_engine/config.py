from dataclasses import dataclass


@dataclass(frozen=True)
class EngineConfig:
    target_utilization: float = 0.85
    max_delta_pct: float = 0.20
    minimum_fleet_size: int = 5
    weak_market_share_pct: float = 9.0
    strong_market_share_pct: float = 15.0
    underutilized_pct: float = 75.0
    high_utilization_pct: float = 90.0


DEFAULT_CONFIG = EngineConfig()

