from typing import Annotated, Any

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from fleet_strategy_engine.assistant.core import (
    ANSWER_SYSTEM_PROMPT,
    MAX_REPAIR_ATTEMPTS,
    REPAIR_SYSTEM_PROMPT,
    VALIDATOR_SYSTEM_PROMPT,
    deterministic_fallback,
    latest_question,
    llm,
    parse_validation_result,
    system_with_context,
    text_from_response,
)


class AssistantState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    context: dict[str, Any]
    answer: str
    validation: dict[str, Any]
    repair_attempts: int
    final_answer: str


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
