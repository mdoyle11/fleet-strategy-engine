# Dashboard

Run the local dashboard with:

```bash
uv run streamlit run dashboard/app.py
```

The dashboard imports the reusable pipeline from `fleet_strategy_engine` and does not duplicate recommendation logic.

## Assistant

The Assistant tab is optional. It elaborates on the deterministic recommendation output using the visible filtered rows, metrics, recommendation scores, confidence, and reason-code reference.

The LLM layer lives in `src/fleet_strategy_engine/assistant.py`, separate from the Streamlit app. It uses LangGraph to orchestrate a compact answer-validation loop:

```text
generate answer -> validate -> repair/retry if needed -> final answer or deterministic fallback
```

If the answer cannot pass validation after the configured retries, the dashboard shows a deterministic summary from the recommendation output instead of exposing the invalid LLM answer.

Set a Gemini API key before launching Streamlit:

```bash
export GOOGLE_API_KEY="..."
```

Or put it in a root-level `.env` file:

```bash
GOOGLE_API_KEY="..."
```

Optionally override the default model:

```bash
export GEMINI_MODEL="gemini-3.5-flash"
```

The `.env` file is ignored by git.
