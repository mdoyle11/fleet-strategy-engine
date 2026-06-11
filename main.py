import argparse
import json
from pathlib import Path

import pandas as pd

from fleet_strategy_engine.pipeline import run_recommendation_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run fleet strategy recommendations.")
    parser.add_argument("--input", required=True, help="Input CSV path.")
    parser.add_argument("--output", required=True, help="Output recommendations CSV path.")
    parser.add_argument(
        "--summary-output",
        required=True,
        help="Output summary JSON path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    summary_path = Path(args.summary_output)
    json_output_path = output_path.with_suffix(".json")

    input_df = pd.read_csv(input_path)
    recommendations_df, summary = run_recommendation_pipeline(input_df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    recommendations_df.to_csv(output_path, index=False)
    recommendations_df.to_json(json_output_path, orient="records", indent=2)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    counts = summary["recommendation_counts"]
    print(
        f"Loaded {summary['row_count']} rows across "
        f"{summary['station_count']} stations and {summary['segment_count']} segments."
    )
    print("Generated recommendations:")
    for action in ("BUY", "HOLD", "REDUCE"):
        print(f"  {action}: {counts[action]}")
    print(f"Wrote {output_path}")
    print(f"Wrote {json_output_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()

