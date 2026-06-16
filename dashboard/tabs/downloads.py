import json
from io import BytesIO, StringIO

import pandas as pd
import streamlit as st


def render_downloads(df: pd.DataFrame, summary: dict) -> None:
    csv_buffer = StringIO()
    parquet_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    df.to_parquet(parquet_buffer, index=False)
    summary_json = json.dumps(summary, indent=2)

    left, middle, right = st.columns(3)
    left.download_button(
        "Download recommendations CSV",
        data=csv_buffer.getvalue(),
        file_name="recommendations.csv",
        mime="text/csv",
    )
    middle.download_button(
        "Download recommendations Parquet",
        data=parquet_buffer.getvalue(),
        file_name="recommendations.parquet",
        mime="application/octet-stream",
    )
    right.download_button(
        "Download summary JSON",
        data=summary_json,
        file_name="summary.json",
        mime="application/json",
    )


