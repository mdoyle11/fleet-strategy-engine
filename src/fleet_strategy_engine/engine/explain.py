import pandas as pd


def add_explanations(df: pd.DataFrame) -> pd.DataFrame:
    explained = df.copy()
    explained["reasoning"] = explained.apply(explain_row, axis=1)
    explained["reason_codes"] = explained["reason_codes"].apply(lambda codes: "|".join(codes))
    return explained


def explain_row(row: pd.Series) -> str:
    recommendation = row["recommendation"]
    util = float(row["utilization_pct"])
    roi = float(row["daily_roi"])
    share = float(row["market_share_pct"])
    delta = int(row["recommended_fleet_delta"])
    price_gap_pct = float(row["price_gap_pct"])

    if recommendation == "BUY":
        text = (
            f"BUY: Utilization is {util:.1f}%, above the capacity threshold, "
            f"and daily ROI is {roi:.1%}. Market share is {share:.1f}%, "
            f"supporting the demand signal. Recommend adding about {delta} vehicles."
        )
    elif recommendation == "REDUCE":
        text = (
            f"REDUCE: Utilization is {util:.1f}%, below the overfleet threshold. "
            f"Daily ROI is {roi:.1%} and market share is {share:.1f}%. "
            f"Recommend reducing by about {abs(delta)} vehicles."
        )
    else:
        text = (
            f"HOLD: Utilization is {util:.1f}% and daily ROI is {roi:.1%}. "
            "Signals are balanced, so keeping the current fleet is the lowest-risk action."
        )

    caveats = []
    if util >= 90 and roi <= 0:
        caveats.append(
            "Although utilization is high, ROI is non-positive, so expansion would scale unprofitable rentals."
        )
    if util >= 90 and price_gap_pct <= -10:
        caveats.append(
            "Because price is materially below the competitor, some demand may be price-driven."
        )
    if util < 75 and share < 9:
        caveats.append(
            "Low utilization and weak share suggest a structural demand issue rather than a fleet shortage."
        )

    if caveats:
        text = f"{text} {' '.join(caveats)}"

    return text
