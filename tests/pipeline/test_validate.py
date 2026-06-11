import pandas as pd
import pytest

from fleet_strategy_engine.pipeline.validate import ValidationError, validate_input


def read_fixture(name: str) -> pd.DataFrame:
    return pd.read_csv(f"tests/fixtures/{name}")


def test_valid_input_passes_validation() -> None:
    validate_input(read_fixture("valid_sample.csv"))


def test_missing_columns_fail_validation() -> None:
    with pytest.raises(ValidationError, match="Missing required columns"):
        validate_input(read_fixture("invalid_missing_columns.csv"))


def test_bad_numeric_values_fail_validation() -> None:
    with pytest.raises(ValidationError):
        validate_input(read_fixture("invalid_bad_values.csv"))


def test_duplicate_station_segment_rows_fail_validation() -> None:
    with pytest.raises(ValidationError, match="duplicate station/segment"):
        validate_input(read_fixture("invalid_duplicate_rows.csv"))


def test_invalid_segment_fails_validation() -> None:
    df = read_fixture("valid_sample.csv")
    df.loc[0, "segment"] = "Convertible"

    with pytest.raises(ValidationError, match="Invalid segment"):
        validate_input(df)

