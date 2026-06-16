import pandas as pd
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from fleet_strategy_engine.assistant import (
    AssistantValidationError,
    build_assistant_context,
    deterministic_fallback,
    fragile_query_tool_request,
    history_to_messages,
    parse_validation_result,
    parse_query_tool_request,
    parse_scenario_tool_request,
    route_after_validation,
)


def recommendation_row(**overrides):
    row = {
        "station": "JFK",
        "region": "Northeast",
        "segment": "SUV",
        "fleet_size": 50,
        "utilization_pct": 92.0,
        "daily_margin": 65.0,
        "daily_roi": 1.1818,
        "estimated_daily_profit": 2830.0,
        "price_gap_pct": -4.0,
        "market_share_pct": 16.0,
        "recommendation": "BUY",
        "recommendation_score": 0.83,
        "confidence": "high",
        "recommended_fleet_delta": 4,
        "pricing_signal": "near_competitor_price",
        "reason_codes": "utilization_above_90|strong_margin",
        "reasoning": "BUY because utilization and ROI are strong.",
    }
    row.update(overrides)
    return row


def test_build_assistant_context_uses_filtered_recommendations() -> None:
    df = pd.DataFrame(
        [
            recommendation_row(),
            recommendation_row(
                station="ORD",
                region="Midwest",
                segment="Economy",
                recommendation="REDUCE",
                recommendation_score=-0.67,
                recommended_fleet_delta=-3,
            ),
        ]
    )

    context = build_assistant_context(df)

    assert context["filtered_summary"]["visible_rows"] == 2
    assert context["filtered_summary"]["recommendation_counts"] == {
        "BUY": 1,
        "HOLD": 0,
        "REDUCE": 1,
    }
    assert context["filtered_summary"]["net_recommended_fleet_delta"] == 1
    assert context["recommendation_rows"][0]["station"] == "JFK"
    assert "reason_codes" in context["reason_code_reference"]


def test_parse_validation_result_requires_boolean_valid_flag() -> None:
    assert parse_validation_result('{"valid": true, "issue": ""}') == {
        "valid": True,
        "issue": "",
    }

    with pytest.raises(AssistantValidationError):
        parse_validation_result('{"valid": "yes", "issue": ""}')

    with pytest.raises(AssistantValidationError):
        parse_validation_result("not json")


def test_history_to_messages_preserves_assistant_context_for_followups() -> None:
    messages = history_to_messages(
        [
            {"role": "user", "content": "Find negative daily profit rows"},
            {"role": "assistant", "content": "SEA / Premium and IAD / Premium are negative."},
        ]
    )

    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)
    assert "SEA / Premium" in str(messages[1].content)


def test_parse_query_tool_request_requires_supported_tool() -> None:
    assert parse_query_tool_request(
        '{"tool": "query_opportunities", "arguments": {"filters": {"region": "West"}}}'
    ) == {
        "tool": "query_opportunities",
        "arguments": {"filters": {"region": "West"}},
        "issue": "",
    }
    assert parse_query_tool_request(
        '{"tool": "lookup_opportunity", "arguments": {"station": "JFK", "segment": "SUV"}}'
    ) == {
        "tool": "lookup_opportunity",
        "arguments": {"station": "JFK", "segment": "SUV"},
        "issue": "",
    }

    with pytest.raises(AssistantValidationError):
        parse_query_tool_request('{"tool": "unsupported", "arguments": {}}')


def test_parse_query_tool_request_accepts_prose_wrapped_json() -> None:
    assert parse_query_tool_request(
        'Use this:\n{"tool": "query_opportunities", "arguments": {"filters": {"station": "ATL", "segment": ["Economy", "SUV"]}}}'
    ) == {
        "tool": "query_opportunities",
        "arguments": {"filters": {"station": "ATL", "segment": ["Economy", "SUV"]}},
        "issue": "",
    }


def test_parse_scenario_tool_request_requires_supported_tool() -> None:
    assert parse_scenario_tool_request(
        '{"tool": "run_rule_scenario", "arguments": {"updates": {"high_utilization_pct": 88}}}'
    ) == {
        "tool": "run_rule_scenario",
        "arguments": {"updates": {"high_utilization_pct": 88}},
        "issue": "",
    }
    assert parse_scenario_tool_request(
        '{"tool": "find_fragile_recommendations", "arguments": {"limit": 3, "recommendation_filter": "BUY"}}'
    ) == {
        "tool": "find_fragile_recommendations",
        "arguments": {"limit": 3, "recommendation_filter": "BUY"},
        "issue": "",
    }

    with pytest.raises(AssistantValidationError):
        parse_scenario_tool_request('{"tool": "delete_everything", "arguments": {}}')


def test_fragile_query_tool_request_routes_buy_queries() -> None:
    request = fragile_query_tool_request("What are the most fragile buy opportunities?")

    assert request == {
        "tool": "find_fragile_recommendations",
        "arguments": {
            "limit": 5,
            "recommendation_filter": "BUY",
            "downside_case": None,
        },
        "issue": "",
    }


def test_fragile_query_tool_request_adds_downside_case() -> None:
    request = fragile_query_tool_request(
        "Find the most fragile BUY opportunities and stress test them."
    )

    assert request["tool"] == "find_fragile_recommendations"
    assert request["arguments"]["recommendation_filter"] == "BUY"
    assert request["arguments"]["downside_case"] == "moderate"


def test_validation_router_retries_then_falls_back() -> None:
    assert route_after_validation(
        {
            "validation": {"valid": True, "issue": ""},
            "repair_attempts": 0,
        }
    ) == "finalize"
    assert route_after_validation(
        {
            "validation": {"valid": False, "issue": "unsupported claim"},
            "repair_attempts": 0,
        }
    ) == "repair_answer"
    assert route_after_validation(
        {
            "validation": {"valid": False, "issue": "unsupported claim"},
            "repair_attempts": 2,
        }
    ) == "fallback"


def test_deterministic_fallback_uses_recommendation_output() -> None:
    df = pd.DataFrame(
        [
            recommendation_row(),
            recommendation_row(
                station="ORD",
                region="Midwest",
                segment="Economy",
                recommendation="REDUCE",
                recommendation_score=-0.67,
                recommended_fleet_delta=-3,
            ),
        ]
    )
    context = build_assistant_context(df)

    fallback = deterministic_fallback(
        context,
        "answer changed the recommendation",
    )

    assert "deterministic summary" in fallback
    assert "BUY / HOLD / REDUCE counts: 1 / 0 / 1" in fallback
    assert "JFK / SUV: BUY" in fallback
    assert "ORD / Economy: REDUCE" in fallback
