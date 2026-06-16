import json
import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from fleet_strategy_engine.assistant.scenario_tools import ScenarioToolError, run_scenario_tool


REASON_CODE_REFERENCE_PATH = Path("docs/reason_code_reference.json")
DEFAULT_MODEL = "gemini-3.5-flash"
MAX_REPAIR_ATTEMPTS = 2

ANSWER_SYSTEM_PROMPT = """
You are an assistant embedded in a fleet strategy dashboard.

The deterministic recommendation engine is the source of truth. Do not change,
override, or invent BUY/HOLD/REDUCE recommendations. Answer only from the
provided filtered dashboard context, metrics, recommendation_score, confidence,
reason_codes, reasoning text, and reason code reference.

If the user asks for information outside the provided data or business logic,
say that the dashboard context does not support that answer.

Provide detailed, planner-facing explanations. Use reason code descriptions to
explain why a decision was made, identify tradeoffs when BUY and REDUCE pressure
coexist, and distinguish recommendation_score from confidence.
"""

QUERY_TOOL_SYSTEM_PROMPT = """
You decide whether a fleet dashboard question needs a deterministic lookup or
filter query before answering.

Return only valid JSON. Do not include markdown or prose.

Available tools:
1. lookup_opportunity
Use for a specific station / segment request.
Shape:
{
  "tool": "lookup_opportunity",
  "arguments": {"station": "ATL", "segment": "SUV"}
}

2. query_opportunities
Use for region, segment, recommendation, confidence, or metric-range queries.
Shape:
{
  "tool": "query_opportunities",
  "arguments": {
    "filters": {
      "region": "West",
      "segment": "SUV",
      "recommendation": "BUY",
      "confidence": "low",
      "utilization_pct": {"min": 90},
      "daily_roi": {"max": 0.25},
      "market_share_pct": {"min": 15}
    },
    "sort_by": "recommendation_score",
    "sort_direction": "desc",
    "limit": 20
  }
}

3. none
Use when the question asks about the current portfolio generally and does not
need a narrower deterministic row set.
Shape:
{"tool": "none", "arguments": {}, "issue": ""}

Only use text/numeric fields listed in the provided context. Use exact available
values where possible. For comparisons between segments at one station, use
query_opportunities with a station filter and a segment list, for example
{"filters": {"station": "ATL", "segment": ["Economy", "SUV"]}}.
For follow-up questions that refer to rows "you just mentioned" or "those cases",
use the recent conversation to infer the deterministic filter or row set. Prefer
metric filters such as {"estimated_daily_profit": {"max": 0}} or
{"daily_roi": {"max": 0}} when the prior answer was based on that condition.
If the user asks for the "top" or "highest" rows, include an appropriate sort_by
and limit. If the user asks for the "lowest", "least", "most unprofitable", or
"worst profitability" rows, sort by estimated_daily_profit ascending.
"""

VALIDATOR_SYSTEM_PROMPT = """
You validate assistant answers for a deterministic fleet recommendation system.

Return only valid JSON with this shape:
{"valid": true | false, "issue": "short explanation"}

An answer is invalid if it:
- changes, overrides, or contradicts the deterministic BUY/HOLD/REDUCE output
- invents metrics, reason codes, rows, stations, or segments absent from context
- recommends actions outside BUY, HOLD, or REDUCE
- claims causal certainty beyond the provided rule-based metrics and reason codes
- answers a question using information outside the provided dashboard context

An answer may discuss tradeoffs and planner next steps if they are grounded in
the provided recommendation output and reason-code reference.
"""

REPAIR_SYSTEM_PROMPT = """
Rewrite the assistant answer so it passes validation.

Rules:
- Keep the deterministic recommendation output as source of truth.
- Do not add new facts.
- Remove or soften unsupported claims.
- Preserve useful explanation grounded in metrics, scores, confidence, and
  reason-code reference.
"""

SCENARIO_TOOL_SYSTEM_PROMPT = """
You are a scenario assistant for a deterministic fleet recommendation dashboard.

Choose exactly one tool call from the user's request and return only valid JSON.
Do not include markdown, prose, or comments.

Available tools:
1. run_rule_scenario
Use when the user wants to change planning rule thresholds.
Arguments shape:
{
  "tool": "run_rule_scenario",
  "arguments": {
    "updates": {
      "target_utilization": 0.85,
      "max_delta_pct": 0.20,
      "weak_market_share_pct": 9,
      "strong_market_share_pct": 15,
      "underutilized_pct": 75,
      "high_utilization_pct": 90,
      "thin_roi_threshold": 0.25,
      "strong_roi_threshold": 0.75
    }
  }
}

2. run_metric_scenario
Use when the user wants to change observed metrics for one station / segment.
Arguments shape:
{
  "tool": "run_metric_scenario",
  "arguments": {
    "station": "ATL",
    "segment": "SUV",
    "updates": {
      "fleet_size": 57,
      "utilization_pct": 87,
      "avg_daily_rate": 145,
      "avg_daily_fleet_cost": 43,
      "avg_daily_operating_cost": 14,
      "competitor_rate": 136,
      "market_share_pct": 16.5
    }
  }
}

3. find_fragile_recommendations
Use when the user asks to find, rank, inspect, or stress-test fragile
recommendations without naming a specific metric update.
Arguments shape:
{
  "tool": "find_fragile_recommendations",
  "arguments": {
    "limit": 5,
    "recommendation_filter": "BUY",
    "downside_case": "moderate"
  }
}
recommendation_filter is optional and must be BUY, HOLD, or REDUCE.
downside_case is optional and must be mild, moderate, or severe. Include
downside_case when the user asks to stress test, test downside, pressure test,
or run scenario analysis on fragile rows.

For find_fragile_recommendations, the user does not need to request a threshold
or metric update. It is a read-only query tool. If the user asks for fragile BUY
opportunities, set recommendation_filter to BUY. If no limit is specified, use 5.

For update tools, only include fields the user explicitly asked to change. If an
update request is ambiguous, return:
{"tool": "none", "arguments": {}, "issue": "what is missing"}

Do not invent station/segment pairs. Use only station/segment pairs visible in the
provided dashboard context.
"""

SCENARIO_ANSWER_SYSTEM_PROMPT = """
You are a scenario assistant embedded in a fleet strategy dashboard.

The deterministic scenario tool result is the source of truth. Explain what was
changed, how the deterministic BUY/HOLD/REDUCE recommendation output changed,
and which reason codes or fragile rows matter. Do not claim that changing price,
cost, utilization, or market share will causally change demand. Describe the
result as a simulated rerun of deterministic logic.
"""


class AssistantConfigurationError(RuntimeError):
    pass


class AssistantValidationError(RuntimeError):
    pass


def load_reason_code_reference(path: Path = REASON_CODE_REFERENCE_PATH) -> dict[str, Any]:
    with path.open() as reference_file:
        return json.load(reference_file)


def filtered_counts(df: pd.DataFrame) -> dict[str, int]:
    counts = df["recommendation"].value_counts()
    return {action: int(counts.get(action, 0)) for action in ("BUY", "HOLD", "REDUCE")}


def build_assistant_context(df: pd.DataFrame) -> dict[str, Any]:
    context_columns = [
        "station",
        "region",
        "segment",
        "fleet_size",
        "utilization_pct",
        "daily_margin",
        "daily_roi",
        "estimated_daily_profit",
        "price_gap_pct",
        "market_share_pct",
        "recommendation",
        "recommendation_score",
        "confidence",
        "recommended_fleet_delta",
        "pricing_signal",
        "reason_codes",
        "reasoning",
    ]
    return {
        "filtered_summary": {
            "visible_rows": int(len(df)),
            "station_count": int(df["station"].nunique()),
            "segment_count": int(df["segment"].nunique()),
            "recommendation_counts": filtered_counts(df),
            "net_recommended_fleet_delta": int(df["recommended_fleet_delta"].sum()),
            "avg_utilization_pct": round(float(df["utilization_pct"].mean()), 2),
            "avg_daily_margin": round(float(df["daily_margin"].mean()), 2),
            "avg_daily_roi": round(float(df["daily_roi"].mean()), 4),
            "total_estimated_daily_profit": round(
                float(df["estimated_daily_profit"].sum()), 2
            ),
            "avg_market_share_pct": round(float(df["market_share_pct"].mean()), 2),
        },
        "reason_code_reference": load_reason_code_reference(),
        "recommendation_rows": df[context_columns].to_dict(orient="records"),
    }


def configured_model_name() -> str:
    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)


def ensure_api_key() -> None:
    if not os.environ.get("GOOGLE_API_KEY"):
        raise AssistantConfigurationError("Set GOOGLE_API_KEY to enable the dashboard assistant.")


def llm() -> ChatGoogleGenerativeAI:
    ensure_api_key()
    return ChatGoogleGenerativeAI(
        model=configured_model_name(),
        temperature=0.2,
    )


def text_from_response(response: BaseMessage) -> str:
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts).strip()
    return str(content)


def system_with_context(prompt: str, context: dict[str, Any]) -> SystemMessage:
    return SystemMessage(
        content=(
            prompt
            + "\n\nFiltered dashboard context:\n"
            + json.dumps(context, default=str)
        )
    )


def parse_validation_result(raw_result: str) -> dict[str, Any]:
    cleaned = raw_result.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AssistantValidationError("Validator returned non-JSON output.") from exc

    if not isinstance(result.get("valid"), bool):
        raise AssistantValidationError("Validator did not return a boolean valid flag.")
    return {
        "valid": result["valid"],
        "issue": str(result.get("issue", "")),
    }


def parse_query_tool_request(raw_result: str) -> dict[str, Any]:
    cleaned = extract_json_object(raw_result)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AssistantValidationError("Query planner returned non-JSON output.") from exc

    tool = result.get("tool")
    if tool not in {"lookup_opportunity", "query_opportunities", "none"}:
        raise AssistantValidationError("Query planner returned an unsupported tool.")
    arguments = result.get("arguments", {})
    if not isinstance(arguments, dict):
        raise AssistantValidationError("Query planner returned invalid tool arguments.")
    return {
        "tool": tool,
        "arguments": arguments,
        "issue": str(result.get("issue", "")),
    }


def extract_json_object(raw_result: str) -> str:
    cleaned = raw_result.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        return cleaned
    return cleaned[start : end + 1]


def parse_scenario_tool_request(raw_result: str) -> dict[str, Any]:
    cleaned = raw_result.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AssistantValidationError("Scenario assistant returned non-JSON output.") from exc

    tool = result.get("tool")
    if tool not in {
        "run_rule_scenario",
        "run_metric_scenario",
        "find_fragile_recommendations",
        "none",
    }:
        raise AssistantValidationError("Scenario assistant returned an unsupported tool.")
    arguments = result.get("arguments", {})
    if not isinstance(arguments, dict):
        raise AssistantValidationError("Scenario assistant returned invalid tool arguments.")
    return {
        "tool": tool,
        "arguments": arguments,
        "issue": str(result.get("issue", "")),
    }


def fragile_query_tool_request(question: str) -> Optional[dict[str, Any]]:
    lowered = question.lower()
    if "fragile" not in lowered:
        return None
    if not any(word in lowered for word in ("find", "most", "show", "what", "which", "rank")):
        return None

    recommendation_filter = None
    if "buy" in lowered:
        recommendation_filter = "BUY"
    elif "hold" in lowered:
        recommendation_filter = "HOLD"
    elif "reduce" in lowered or "reduction" in lowered:
        recommendation_filter = "REDUCE"

    downside_case = None
    if "severe" in lowered:
        downside_case = "severe"
    elif "moderate" in lowered:
        downside_case = "moderate"
    elif "mild" in lowered:
        downside_case = "mild"
    elif any(term in lowered for term in ("downside", "stress", "pressure test", "scenario analysis")):
        downside_case = "moderate"

    return {
        "tool": "find_fragile_recommendations",
        "arguments": {
            "limit": 5,
            "recommendation_filter": recommendation_filter,
            "downside_case": downside_case,
        },
        "issue": "",
    }


def latest_question(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def deterministic_fallback(context: dict[str, Any], validation_issue: str) -> str:
    summary = context["filtered_summary"]
    counts = summary["recommendation_counts"]
    rows = context["recommendation_rows"]

    top_buy_rows = sorted(
        [row for row in rows if row["recommendation"] == "BUY"],
        key=lambda row: row["recommendation_score"],
        reverse=True,
    )[:3]
    top_reduce_rows = sorted(
        [row for row in rows if row["recommendation"] == "REDUCE"],
        key=lambda row: row["recommendation_score"],
    )[:3]

    def row_summary(row: dict[str, Any]) -> str:
        return (
            f"- {row['station']} / {row['segment']}: {row['recommendation']} "
            f"(score {row['recommendation_score']:+.2f}, confidence {row['confidence']}, "
            f"delta {int(row['recommended_fleet_delta']):+})"
        )

    buy_summary = "\n".join(row_summary(row) for row in top_buy_rows) or "- None in current filters"
    reduce_summary = (
        "\n".join(row_summary(row) for row in top_reduce_rows)
        or "- None in current filters"
    )

    return (
        "I could not produce a validated LLM response, so I am showing a deterministic "
        "summary from the recommendation output instead.\n\n"
        f"Validation issue: {validation_issue or 'response did not pass guardrails'}\n\n"
        f"Visible rows: {summary['visible_rows']}\n"
        f"BUY / HOLD / REDUCE counts: {counts['BUY']} / {counts['HOLD']} / {counts['REDUCE']}\n"
        f"Average utilization: {summary['avg_utilization_pct']:.1f}%\n"
        f"Average daily ROI: {summary['avg_daily_roi']:.1%}\n"
        f"Average market share: {summary['avg_market_share_pct']:.1f}%\n"
        f"Net recommended fleet delta: {summary['net_recommended_fleet_delta']:+}\n\n"
        "Top BUY rows by recommendation score:\n"
        f"{buy_summary}\n\n"
        "Top REDUCE rows by recommendation score:\n"
        f"{reduce_summary}"
    )


def history_to_messages(chat_history: list[dict[str, str]]) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for message in chat_history[-8:]:
        if message["role"] == "user":
            messages.append(HumanMessage(content=message["content"]))
        elif message["role"] == "assistant":
            messages.append(AIMessage(content=message["content"]))
    return messages


def answer_question(
    question: str,
    df: pd.DataFrame,
    chat_history: list[dict[str, str]],
) -> str:
    from fleet_strategy_engine.assistant.graph import build_assistant_graph

    try:
        final_state = build_assistant_graph().invoke(
            {
                "messages": [*history_to_messages(chat_history), HumanMessage(content=question)],
                "context": build_assistant_context(df),
                "source_df": df,
                "query_request": {"tool": "none", "arguments": {}, "issue": ""},
                "answer": "",
                "validation": {"valid": False, "issue": ""},
                "repair_attempts": 0,
                "final_answer": "",
            }
        )
    except AssistantConfigurationError:
        raise
    except Exception as exc:
        message = str(exc)
        if "API_KEY_INVALID" in message or "API key not valid" in message:
            raise RuntimeError(
                "Gemini rejected the API key. Check that GOOGLE_API_KEY in your "
                ".env file is a valid Gemini API key, then restart Streamlit."
            ) from exc
        raise RuntimeError(f"Gemini assistant request failed: {message}") from exc
    return final_state["final_answer"]


def available_opportunities(df: pd.DataFrame) -> list[dict[str, str]]:
    return (
        df[["station", "segment"]]
        .drop_duplicates()
        .sort_values(["station", "segment"])
        .to_dict(orient="records")
    )


def scenario_tool_context(df: pd.DataFrame, scope: str) -> dict[str, Any]:
    return {
        "scope": scope,
        "available_opportunities": available_opportunities(df),
        "allowed_rule_fields": [
            "target_utilization",
            "max_delta_pct",
            "weak_market_share_pct",
            "strong_market_share_pct",
            "underutilized_pct",
            "high_utilization_pct",
            "thin_roi_threshold",
            "strong_roi_threshold",
        ],
        "allowed_metric_fields": [
            "fleet_size",
            "utilization_pct",
            "avg_daily_rate",
            "avg_daily_fleet_cost",
            "avg_daily_operating_cost",
            "competitor_rate",
            "market_share_pct",
        ],
        "available_read_only_tools": [
            "find_fragile_recommendations",
        ],
        "available_downside_cases": ["mild", "moderate", "severe"],
    }


def deterministic_scenario_fallback(result: dict[str, Any]) -> str:
    if result.get("tool") == "run_rule_scenario":
        counts = result["scenario_counts"]
        return (
            "Scenario tool result:\n\n"
            f"Changed rows: {result['changed_row_count']}\n"
            f"Scenario BUY / HOLD / REDUCE counts: "
            f"{counts['BUY']} / {counts['HOLD']} / {counts['REDUCE']}\n"
            f"Net fleet delta changed from {result['baseline_net_delta']:+} "
            f"to {result['scenario_net_delta']:+}.\n"
            "This is a deterministic rule rerun, not a demand forecast."
        )
    if result.get("tool") == "find_fragile_recommendations":
        rows = result.get("fragile_rows", [])
        if not rows:
            return "No matching fragile recommendations were found in the current filters."
        top = rows[0]
        text = (
            "Fragile recommendation scan:\n\n"
            f"Top match: {top['station']} / {top['segment']} "
            f"({top['recommendation']}, score {top['recommendation_score']:+.2f}). "
            f"Its score margin to an action change is "
            f"{top['score_margin_to_action_change']:.2f}, with nearest threshold "
            f"{top['nearest_rule_threshold']} "
            f"({top['nearest_threshold_distance']:.2f} pts away)."
        )
        if result.get("downside_results"):
            downside = result["downside_results"][0]
            text += (
                "\n\nDownside rerun: "
                f"{downside['station']} / {downside['segment']} changed from "
                f"{downside['current']['recommendation']} to "
                f"{downside['scenario']['recommendation']} with score change "
                f"{downside['score_change']:+.2f}."
            )
        return text
    scenario = result["scenario"]
    current = result["current"]
    return (
        "Scenario tool result:\n\n"
        f"{result['station']} / {result['segment']} changed from "
        f"{current['recommendation']} to {scenario['recommendation']} "
        f"with score change {result['score_change']:+.2f} and fleet delta change "
        f"{result['delta_change']:+}.\n"
        "This is a deterministic metric rerun, not a demand forecast."
    )


def answer_scenario_question(
    question: str,
    df: pd.DataFrame,
    chat_history: list[dict[str, str]],
    scope: str,
) -> str:
    context = scenario_tool_context(df, scope)
    try:
        tool_request = fragile_query_tool_request(question)
        if tool_request is None:
            tool_response = llm().invoke(
                [
                    system_with_context(SCENARIO_TOOL_SYSTEM_PROMPT, context),
                    *history_to_messages(chat_history),
                    HumanMessage(content=question),
                ]
            )
            tool_request = parse_scenario_tool_request(text_from_response(tool_response))
        if tool_request["tool"] == "none":
            return tool_request["issue"] or "Please specify the scenario to run."

        if scope == "rules" and tool_request["tool"] not in {
            "run_rule_scenario",
            "find_fragile_recommendations",
        }:
            return "This rules scenario assistant can change rule thresholds or find fragile recommendations."
        if scope == "metrics" and tool_request["tool"] not in {
            "run_metric_scenario",
            "find_fragile_recommendations",
        }:
            return "This metrics scenario assistant can change opportunity metrics or find fragile recommendations."

        tool_result = run_scenario_tool(
            df,
            tool_request["tool"],
            tool_request["arguments"],
        )
        answer_response = llm().invoke(
            [
                system_with_context(
                    SCENARIO_ANSWER_SYSTEM_PROMPT,
                    {
                        "scenario_tool_request": tool_request,
                        "scenario_tool_result": tool_result,
                    },
                ),
                HumanMessage(content=question),
            ]
        )
        answer = text_from_response(answer_response)
        if answer:
            return answer
        return deterministic_scenario_fallback(tool_result)
    except AssistantConfigurationError:
        raise
    except (AssistantValidationError, ScenarioToolError) as exc:
        return str(exc)
    except Exception as exc:
        message = str(exc)
        if "API_KEY_INVALID" in message or "API key not valid" in message:
            raise RuntimeError(
                "Gemini rejected the API key. Check that GOOGLE_API_KEY in your "
                ".env file is a valid Gemini API key, then restart Streamlit."
            ) from exc
        raise RuntimeError(f"Gemini scenario assistant request failed: {message}") from exc
