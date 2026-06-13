import json
import subprocess
from pathlib import Path

import pandas as pd


def test_cli_writes_parquet_csv_and_summary(tmp_path: Path) -> None:
    parquet_path = tmp_path / "recommendations.parquet"
    csv_path = tmp_path / "recommendations.csv"
    summary_path = tmp_path / "summary.json"

    result = subprocess.run(
        [
            "python",
            "main.py",
            "--input",
            "tests/fixtures/valid_sample.csv",
            "--output",
            str(parquet_path),
            "--csv-output",
            str(csv_path),
            "--summary-output",
            str(summary_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    parquet_df = pd.read_parquet(parquet_path)
    csv_df = pd.read_csv(csv_path)
    summary = json.loads(summary_path.read_text())

    assert len(parquet_df) == 3
    assert len(csv_df) == 3
    assert summary["row_count"] == 3
    assert "Wrote" in result.stdout
