import os
from urllib.parse import unquote_plus

from fleet_strategy_engine.pipeline import (
    run_recommendation_file_pipeline,
    write_latest_run_pointer,
)


RAW_UPLOAD_PREFIX_ENV = "FLEET_RAW_UPLOAD_PREFIX"
PROCESSED_BASE_URI_ENV = "FLEET_PROCESSED_BASE_URI"
DEFAULT_RAW_UPLOAD_PREFIX = "raw/uploads/"


def handler(event: dict, context: object) -> dict:
    processed_base_uri = os.environ[PROCESSED_BASE_URI_ENV].rstrip("/")
    raw_prefix = os.environ.get(RAW_UPLOAD_PREFIX_ENV, DEFAULT_RAW_UPLOAD_PREFIX)

    results = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        if not key.startswith(raw_prefix) or not key.endswith("/input.csv"):
            results.append({"key": key, "status": "skipped"})
            continue

        run_id = _run_id_from_key(key, raw_prefix)
        input_uri = f"s3://{bucket}/{key}"
        output_uri = f"{processed_base_uri}/{run_id}"
        recommendations, summary = run_recommendation_file_pipeline(input_uri, output_uri)
        if run_id != "sample":
            write_latest_run_pointer(processed_base_uri, run_id)

        results.append(
            {
                "key": key,
                "run_id": run_id,
                "output_uri": output_uri,
                "row_count": len(recommendations),
                "summary_row_count": summary["row_count"],
                "status": "processed",
            }
        )

    return {"results": results}


def _run_id_from_key(key: str, raw_prefix: str) -> str:
    relative_key = key[len(raw_prefix):]
    parts = relative_key.split("/")
    if len(parts) != 2 or parts[1] != "input.csv" or not parts[0]:
        raise ValueError(f"Cannot derive run_id from S3 key: {key}")
    return parts[0]
