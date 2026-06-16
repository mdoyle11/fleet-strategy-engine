from typing import Annotated, Any

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from fleet_strategy_engine.assistant.core import (
    AssistantValidationError,
    MAX_REPAIR_ATTEMPTS,
    deterministic_fallback,
    latest_question,
    load_reason_code_reference,
    llm,
    parse_query_tool_request,
    parse_validation_result,
    system_with_context,
    text_from_response,
)
from fleet_strategy_engine.assistant.prompts import (
    ANSWER_SYSTEM_PROMPT,
    QUERY_TOOL_SYSTEM_PROMPT,
    REPAIR_SYSTEM_PROMPT,
    VALIDATOR_SYSTEM_PROMPT,
)
from fleet_strategy_engine.assistant.query_tools import (
    QueryToolError,
    planning_context,
    run_query_tool,
)


class AssistantState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    context: dict[str, Any]
    source_df: Any
    query_request: dict[str, Any]
    answer: str
    validation: dict[str, Any]
    repair_attempts: int
    final_answer: str


def plan_query_node(state: AssistantState) -> dict[str, Any]:
    response = llm().invoke(
        [
            system_with_context(QUERY_TOOL_SYSTEM_PROMPT, planning_context(state["source_df"])),
            *state["messages"][-6:],
        ]
    )
    try:
        return {"query_request": parse_query_tool_request(text_from_response(response))}
    except AssistantValidationError as exc:
        return {
            "query_request": {
                "tool": "none",
                "arguments": {},
                "issue": str(exc),
            }
        }


def execute_query_node(state: AssistantState) -> dict[str, Any]:
    try:
        result = run_query_tool(
            state["source_df"],
            state["query_request"]["tool"],
            state["query_request"].get("arguments", {}),
        )
        return {
            "context": {
                "filtered_summary": result.get("summary", {}),
                "reason_code_reference": load_reason_code_reference(),
                "query_tool_request": state["query_request"],
                "query_tool_result": result,
                "recommendation_rows": result.get("rows", []),
            }
        }
    except QueryToolError as exc:
        return {
            "context": {
                **state["context"],
                "query_tool_request": state["query_request"],
                "query_tool_error": str(exc),
            }
        }


def generate_answer_node(state: AssistantState) -> dict[str, Any]:
    question = latest_question(state["messages"])
    response = llm().invoke(
        [
            system_with_context(ANSWER_SYSTEM_PROMPT, state["context"]),
            HumanMessage(content=question),
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


def route_after_query_plan(state: AssistantState) -> str:
    if state["query_request"].get("tool") in {"lookup_opportunity", "query_opportunities"}:
        return "execute_query"
    return "generate_answer"
