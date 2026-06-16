import json
import os
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


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


class AssistantConfigurationError(RuntimeError):
    pass


class AssistantValidationError(RuntimeError):
    pass


class AssistantState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    context: dict[str, Any]
    answer: str
    validation: dict[str, Any]
    repair_attempts: int
    final_answer: str


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


def generate_answer_node(state: AssistantState) -> dict[str, Any]:
    response = llm().invoke(
        [
            system_with_context(ANSWER_SYSTEM_PROMPT, state["context"]),
            *state["messages"][-8:],
        ]
    )
    return {"answer": text_from_response(response)}


def validate_answer_node(state: AssistantState) -> dict[str, Any]:
    question = latest_question(state["messages"])
    response = llm().invoke(
        [
            system_with_context(VALIDATOR_SYSTEM_PROMPT, state["context"]),
            HumanMessage(
                content=(
                    f"User question:\n{question}\n\n"
                    f"Assistant answer to validate:\n{state['answer']}"
                )
            ),
        ]
    )
    return {"validation": parse_validation_result(text_from_response(response))}


def repair_answer_node(state: AssistantState) -> dict[str, Any]:
    question = latest_question(state["messages"])
    response = llm().invoke(
        [
            system_with_context(REPAIR_SYSTEM_PROMPT, state["context"]),
            HumanMessage(
                content=(
                    f"User question:\n{question}\n\n"
                    f"Validation issue:\n{state['validation'].get('issue', '')}\n\n"
                    f"Draft answer:\n{state['answer']}"
                )
            ),
        ]
    )
    return {
        "answer": text_from_response(response),
        "repair_attempts": state["repair_attempts"] + 1,
    }


def fallback_node(state: AssistantState) -> dict[str, Any]:
    return {
        "final_answer": deterministic_fallback(
            state["context"],
            state["validation"].get("issue", ""),
        )
    }


def finalize_node(state: AssistantState) -> dict[str, Any]:
    return {"final_answer": state["answer"]}


def route_after_validation(state: AssistantState) -> str:
    if state["validation"].get("valid"):
        return "finalize"
    if state["repair_attempts"] < MAX_REPAIR_ATTEMPTS:
        return "repair_answer"
    return "fallback"


def build_assistant_graph():
    graph = StateGraph(AssistantState)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("validate_answer", validate_answer_node)
    graph.add_node("repair_answer", repair_answer_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("generate_answer")
    graph.add_edge("generate_answer", "validate_answer")
    graph.add_conditional_edges(
        "validate_answer",
        route_after_validation,
        {
            "finalize": "finalize",
            "repair_answer": "repair_answer",
            "fallback": "fallback",
        },
    )
    graph.add_edge("repair_answer", "validate_answer")
    graph.add_edge("fallback", END)
    graph.add_edge("finalize", END)
    return graph.compile()


def history_to_messages(chat_history: list[dict[str, str]]) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for message in chat_history[-8:]:
        if message["role"] == "user":
            messages.append(HumanMessage(content=message["content"]))
    return messages


def answer_question(
    question: str,
    df: pd.DataFrame,
    chat_history: list[dict[str, str]],
) -> str:
    try:
        final_state = build_assistant_graph().invoke(
            {
                "messages": [*history_to_messages(chat_history), HumanMessage(content=question)],
                "context": build_assistant_context(df),
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
