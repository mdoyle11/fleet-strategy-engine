from langgraph.graph import END, StateGraph

from fleet_strategy_engine.assistant.nodes import (
    AssistantState,
    execute_query_node,
    fallback_node,
    finalize_node,
    generate_answer_node,
    plan_query_node,
    repair_answer_node,
    route_after_query_plan,
    route_after_validation,
    validate_answer_node,
)


def build_assistant_graph():
    graph = StateGraph(AssistantState)
    graph.add_node("plan_query", plan_query_node)
    graph.add_node("execute_query", execute_query_node)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("validate_answer", validate_answer_node)
    graph.add_node("repair_answer", repair_answer_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("plan_query")
    graph.add_conditional_edges(
        "plan_query",
        route_after_query_plan,
        {
            "execute_query": "execute_query",
            "generate_answer": "generate_answer",
        },
    )
    graph.add_edge("execute_query", "generate_answer")
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
