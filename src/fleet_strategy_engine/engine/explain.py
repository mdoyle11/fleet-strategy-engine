import pandas as pd


def add_explanations(df: pd.DataFrame) -> pd.DataFrame:
    explained = df.copy()
    explained["reasoning"] = explained.apply(explain_row, axis=1)
    explained["reason_codes"] = explained["reason_codes"].apply(lambda codes: "|".join(codes))
    explained["pricing_reason_codes"] = explained["pricing_reason_codes"].apply(
        lambda codes: "|".join(codes)
    )
    return explained


def explain_row(row: pd.Series) -> str:
    recommendation = row["recommendation"]
    util = float(row["utilization_pct"])
    margin = float(row["daily_margin"])
    share = float(row["market_share_pct"])
    delta = int(row["recommended_fleet_delta"])
    price_gap_pct = float(row["price_gap_pct"])
    pricing_action = row["pricing_action"]

    if recommendation == "BUY":
        text = (
            f"BUY: Utilization is {util:.1f}%, above the capacity threshold, "
            f"and daily margin is ${margin:.2f}. Market share is {share:.1f}%, "
            f"supporting the demand signal. Recommend adding about {delta} vehicles."
        )
    elif recommendation == "REDUCE":
        text = (
            f"REDUCE: Utilization is {util:.1f}%, below the overfleet threshold. "
            f"Daily margin is ${margin:.2f} and market share is {share:.1f}%. "
            f"Recommend reducing by about {abs(delta)} vehicles."
        )
    else:
        text = (
            f"HOLD: Utilization is {util:.1f}% and daily margin is ${margin:.2f}. "
            "Signals are balanced, so keeping the current fleet is the lowest-risk action."
        )

    caveats = []
    if util >= 90 and margin <= 0:
        caveats.append(
            "Although utilization is high, margin is non-positive, so expansion would scale unprofitable rentals."
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

    return f"{text} Pricing guidance: {pricing_explanation(pricing_action, price_gap_pct, util, margin)}"


def pricing_explanation(
    pricing_action: str,
    price_gap_pct: float,
    utilization_pct: float,
    daily_margin: float,
) -> str:
    if pricing_action == "RAISE_PRICE_TEST":
        return (
            f"test a rate increase because price is {abs(price_gap_pct):.1f}% below competitor "
            f"while utilization is {utilization_pct:.1f}% and margin is ${daily_margin:.2f}."
        )
    if pricing_action == "HOLD_PRICE":
        return (
            f"current pricing appears defensible because price is {price_gap_pct:.1f}% versus competitor "
            f"and utilization remains {utilization_pct:.1f}%."
        )
    if pricing_action == "PRICE_COMPETITIVENESS_REVIEW":
        return (
            f"review pricing and cost position because price gap is {price_gap_pct:.1f}% "
            f"and daily margin is ${daily_margin:.2f}."
        )
    return "monitor price because pricing, utilization, and margin signals are balanced."
