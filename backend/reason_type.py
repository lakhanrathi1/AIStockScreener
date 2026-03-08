from __future__ import annotations


def classify_reason_type(reason: str) -> str:
    text = (reason or "").lower()

    if any(k in text for k in ("result", "earnings", "q1", "q2", "q3", "q4", "profit")):
        return "Earnings"
    if any(k in text for k in ("order", "contract", "tender", "project", "deal won")):
        return "Order/Contract"
    if any(k in text for k in ("merger", "acquisition", "buyback", "stake", "open offer")):
        return "Corporate Action"
    if any(k in text for k in ("upgrade", "downgrade", "target price", "broker")):
        return "Broker Action"
    if any(k in text for k in ("sebi", "regulator", "penalty", "probe", "investigation")):
        return "Regulatory"
    if any(k in text for k in ("fall", "declined", "down", "drop", "weak")):
        return "Negative Momentum"
    return "General News"
