import pandas as pd

from fleet_strategy_engine.schemas import NUMERIC_COLUMNS, REQUIRED_COLUMNS, VALID_SEGMENTS


class ValidationError(ValueError):
    """Raised when an input batch cannot be processed safely."""


def validate_input(df: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValidationError(f"Missing required columns: {', '.join(missing)}")

    required = df[REQUIRED_COLUMNS]
    null_columns = [column for column in REQUIRED_COLUMNS if required[column].isna().any()]
    if null_columns:
        raise ValidationError(f"Required columns contain null values: {', '.join(null_columns)}")

    blank_text = [
        column
        for column in ("station", "segment")
        if required[column].astype(str).str.strip().eq("").any()
    ]
    if blank_text:
        raise ValidationError(f"Required text columns contain blanks: {', '.join(blank_text)}")

    invalid_segments = sorted(set(required["segment"]) - VALID_SEGMENTS)
    if invalid_segments:
        raise ValidationError(f"Invalid segment values: {', '.join(map(str, invalid_segments))}")

    for column in NUMERIC_COLUMNS:
        converted = pd.to_numeric(required[column], errors="coerce")
        if converted.isna().any():
            raise ValidationError(f"Column must be numeric: {column}")

    numeric = required[NUMERIC_COLUMNS].apply(pd.to_numeric)
    if (numeric["fleet_size"] <= 0).any():
        raise ValidationError("fleet_size must be positive")
    if ((numeric["utilization_pct"] < 0) | (numeric["utilization_pct"] > 100)).any():
        raise ValidationError("utilization_pct must be between 0 and 100")
    if ((numeric["market_share_pct"] < 0) | (numeric["market_share_pct"] > 100)).any():
        raise ValidationError("market_share_pct must be between 0 and 100")
    if (numeric["competitor_rate"] <= 0).any():
        raise ValidationError("competitor_rate must be positive")

    non_negative = ["avg_daily_rate", "avg_daily_fleet_cost", "avg_daily_operating_cost"]
    invalid_non_negative = [column for column in non_negative if (numeric[column] < 0).any()]
    if invalid_non_negative:
        raise ValidationError(f"Columns must be non-negative: {', '.join(invalid_non_negative)}")

    duplicates = required.duplicated(subset=["station", "segment"])
    if duplicates.any():
        raise ValidationError("Input contains duplicate station/segment rows")

