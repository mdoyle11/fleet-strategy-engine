from fleet_strategy_engine.aws import lambda_handler


def test_lambda_handler_processes_raw_upload_event(monkeypatch) -> None:
    calls = []
    pointer_calls = []

    def fake_run_pipeline(input_uri: str, output_uri: str):
        calls.append((input_uri, output_uri))
        return [object(), object()], {"row_count": 2}

    monkeypatch.setenv(
        "FLEET_PROCESSED_BASE_URI",
        "s3://fleet-strategy/processed/runs",
    )
    monkeypatch.setattr(
        lambda_handler,
        "run_recommendation_file_pipeline",
        fake_run_pipeline,
    )
    monkeypatch.setattr(
        lambda_handler,
        "write_latest_run_pointer",
        lambda base_uri, run_id: pointer_calls.append((base_uri, run_id)),
    )

    result = lambda_handler.handler(
        {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "fleet-strategy"},
                        "object": {"key": "raw/uploads/run-123/input.csv"},
                    }
                }
            ]
        },
        None,
    )

    assert calls == [
        (
            "s3://fleet-strategy/raw/uploads/run-123/input.csv",
            "s3://fleet-strategy/processed/runs/run-123",
        )
    ]
    assert result["results"][0]["status"] == "processed"
    assert result["results"][0]["row_count"] == 2
    assert pointer_calls == [
        ("s3://fleet-strategy/processed/runs", "run-123")
    ]


def test_lambda_handler_does_not_mark_sample_as_latest(monkeypatch) -> None:
    pointer_calls = []

    monkeypatch.setenv(
        "FLEET_PROCESSED_BASE_URI",
        "s3://fleet-strategy/processed/runs",
    )
    monkeypatch.setattr(
        lambda_handler,
        "run_recommendation_file_pipeline",
        lambda input_uri, output_uri: ([object()], {"row_count": 1}),
    )
    monkeypatch.setattr(
        lambda_handler,
        "write_latest_run_pointer",
        lambda base_uri, run_id: pointer_calls.append((base_uri, run_id)),
    )

    lambda_handler.handler(
        {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "fleet-strategy"},
                        "object": {"key": "raw/uploads/sample/input.csv"},
                    }
                }
            ]
        },
        None,
    )

    assert pointer_calls == []


def test_lambda_handler_skips_unrelated_objects(monkeypatch) -> None:
    monkeypatch.setenv(
        "FLEET_PROCESSED_BASE_URI",
        "s3://fleet-strategy/processed/runs",
    )

    result = lambda_handler.handler(
        {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "fleet-strategy"},
                        "object": {"key": "processed/runs/run-123/summary.json"},
                    }
                }
            ]
        },
        None,
    )

    assert result["results"] == [
        {"key": "processed/runs/run-123/summary.json", "status": "skipped"}
    ]
