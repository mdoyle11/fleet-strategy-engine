REQUIRED_COLUMNS = [
    "station",
    "segment",
    "fleet_size",
    "utilization_pct",
    "avg_daily_rate",
    "avg_daily_fleet_cost",
    "avg_daily_operating_cost",
    "competitor_rate",
    "market_share_pct",
]

NUMERIC_COLUMNS = [
    "fleet_size",
    "utilization_pct",
    "avg_daily_rate",
    "avg_daily_fleet_cost",
    "avg_daily_operating_cost",
    "competitor_rate",
    "market_share_pct",
]

VALID_SEGMENTS = {"Economy", "SUV", "Premium", "Minivan", "Truck"}

OUTPUT_COLUMNS = [
    "station",
    "segment",
    "fleet_size",
    "utilization_pct",
    "avg_daily_rate",
    "avg_daily_fleet_cost",
    "avg_daily_operating_cost",
    "competitor_rate",
    "market_share_pct",
    "daily_margin",
    "price_gap",
    "price_gap_pct",
    "estimated_rented_cars",
    "target_fleet_at_85_util",
    "recommended_fleet_delta",
    "utilization_band",
    "margin_band",
    "pricing_signal",
    "market_share_signal",
    "recommendation",
    "confidence",
    "buy_score",
    "reduce_score",
    "reason_codes",
    "reasoning",
]
