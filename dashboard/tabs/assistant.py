import importlib
import os

import pandas as pd
import streamlit as st

import fleet_strategy_engine.assistant as assistant_module
from fleet_strategy_engine.assistant import (
    AssistantConfigurationError,
    AssistantValidationError,
    answer_question,
)


def configure_assistant_environment() -> bool:
    try:
        secret_key = st.secrets.get("GOOGLE_API_KEY", "")
        secret_model = st.secrets.get("GEMINI_MODEL", "")
    except Exception:
        secret_key = ""
        secret_model = ""

    if secret_key:
        os.environ["GOOGLE_API_KEY"] = secret_key
    if secret_model:
        os.environ["GEMINI_MODEL"] = secret_model
    return bool(os.environ.get("GOOGLE_API_KEY"))


def render_assistant(df: pd.DataFrame) -> None:
    st.subheader("Decision Assistant")
    st.caption(
        "Answers are constrained to the deterministic recommendations, metrics, "
        "scores, confidence, and reason-code reference for the current filters."
    )

    if "assistant_messages" not in st.session_state:
        st.session_state["assistant_messages"] = [
            {
                "role": "assistant",
                "content": (
                    "Ask about the current recommendations, why specific station "
                    "segments are BUY/HOLD/REDUCE, or what themes appear in the "
                    "filtered portfolio."
                ),
            }
        ]

    for message in st.session_state["assistant_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if not configure_assistant_environment():
        st.info("Set GOOGLE_API_KEY to enable the dashboard assistant.")
        return

    question = st.chat_input("Ask about the current recommendation output")
    if not question:
        return

    st.session_state["assistant_messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Reviewing filtered recommendations..."):
            try:
                answer = answer_question(
                    question,
                    df,
                    st.session_state["assistant_messages"][:-1],
                )
            except (
                AssistantConfigurationError,
                AssistantValidationError,
                RuntimeError,
                Exception,
            ) as exc:
                answer = str(exc)
            st.markdown(answer)

    st.session_state["assistant_messages"].append(
        {"role": "assistant", "content": answer}
    )


def render_scenario_assistant(df: pd.DataFrame, scope: str) -> None:
    title = "Rule Scenario Assistant" if scope == "rules" else "Metric Scenario Assistant"
    placeholder = (
        "Example: set high utilization threshold to 88 and strong market share to 13"
        if scope == "rules"
        else "Example: for ATL / SUV, set avg daily rate to 145 and utilization to 87"
    )
    state_key = f"{scope}_scenario_messages"
    input_key = f"{scope}_scenario_request"

    st.markdown(f"##### {title}")
    st.caption(
        "The assistant can call deterministic scenario tools and explain the rerun. "
        "It does not update the source recommendations or estimate causal demand response."
    )

    if state_key not in st.session_state:
        st.session_state[state_key] = []

    for message in st.session_state[state_key][-4:]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    request = st.text_area("Scenario request", placeholder=placeholder, key=input_key)
    run_requested = st.button(
        "Run scenario with assistant",
        key=f"{scope}_scenario_button",
        type="secondary",
    )
    if not run_requested:
        return
    if not request.strip():
        st.info("Enter a scenario request first.")
        return
    if not configure_assistant_environment():
        st.info("Set GOOGLE_API_KEY to enable the scenario assistant.")
        return

    st.session_state[state_key].append({"role": "user", "content": request})
    with st.chat_message("user"):
        st.markdown(request)

    with st.chat_message("assistant"):
        with st.spinner("Running deterministic scenario tool..."):
            try:
                scenario_assistant = importlib.reload(assistant_module)
                answer = scenario_assistant.answer_scenario_question(
                    request,
                    df,
                    st.session_state[state_key][:-1],
                    scope,
                )
            except (
                AssistantConfigurationError,
                AssistantValidationError,
                RuntimeError,
                Exception,
            ) as exc:
                answer = str(exc)
            st.markdown(answer)

    st.session_state[state_key].append({"role": "assistant", "content": answer})


