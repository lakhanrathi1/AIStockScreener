from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st


def _load_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date

    for col in ("percent_change", "confidence", "pnl_pct", "hit"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def main() -> None:
    st.set_page_config(page_title="AI Stock Reason Dashboard", layout="wide")
    st.title("AI Stock Reason Dashboard")

    history_path = Path(os.getenv("ALERT_HISTORY_PATH", "data/alerts_history.csv"))
    df = _load_history(history_path)

    if df.empty:
        st.warning(f"No data found at `{history_path}`. Run the daily job first.")
        return

    required_cols = [
        "trade_date",
        "symbol",
        "sector",
        "reason_type",
        "confidence",
        "pnl_pct",
        "hit",
    ]
    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    st.sidebar.header("Filters")

    min_date = df["trade_date"].dropna().min()
    max_date = df["trade_date"].dropna().max()
    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    filtered = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]

    symbol_opts = sorted(x for x in filtered["symbol"].dropna().unique())
    sector_opts = sorted(x for x in filtered["sector"].dropna().unique())
    reason_type_opts = sorted(x for x in filtered["reason_type"].dropna().unique())

    symbols = st.sidebar.multiselect("Symbol", symbol_opts, default=symbol_opts)
    sectors = st.sidebar.multiselect("Sector", sector_opts, default=sector_opts)
    reason_types = st.sidebar.multiselect("Reason Type", reason_type_opts, default=reason_type_opts)

    filtered = filtered[
        filtered["symbol"].isin(symbols)
        & filtered["sector"].isin(sectors)
        & filtered["reason_type"].isin(reason_types)
    ]

    pnl_series = filtered["pnl_pct"].dropna()
    pnl_min = float(pnl_series.min()) if not pnl_series.empty else -20.0
    pnl_max = float(pnl_series.max()) if not pnl_series.empty else 20.0
    pnl_range = st.sidebar.slider("PnL % range", pnl_min, pnl_max, (pnl_min, pnl_max))
    filtered = filtered[
        filtered["pnl_pct"].isna()
        | ((filtered["pnl_pct"] >= pnl_range[0]) & (filtered["pnl_pct"] <= pnl_range[1]))
    ]

    hit_df = filtered.dropna(subset=["hit"]).copy()
    hit_rate_by_symbol = (
        hit_df.groupby("symbol", as_index=False)["hit"].mean().rename(columns={"hit": "hit_rate"})
    )
    hit_rate_by_symbol["hit_rate"] = hit_rate_by_symbol["hit_rate"] * 100.0

    min_hit_rate, max_hit_rate = st.sidebar.slider("Hit-rate %", 0, 100, (0, 100))
    if not hit_rate_by_symbol.empty:
        valid_symbols = set(
            hit_rate_by_symbol[
                (hit_rate_by_symbol["hit_rate"] >= min_hit_rate)
                & (hit_rate_by_symbol["hit_rate"] <= max_hit_rate)
            ]["symbol"]
        )
        unknown_symbols = set(filtered[filtered["hit"].isna()]["symbol"])
        filtered = filtered[filtered["symbol"].isin(valid_symbols | unknown_symbols)]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Alerts", len(filtered))
    c2.metric("Avg Confidence", f"{filtered['confidence'].dropna().mean():.1f}%")
    c3.metric("Avg PnL", f"{filtered['pnl_pct'].dropna().mean():.2f}%")
    c4.metric("Hit-rate", f"{(hit_df['hit'].mean() * 100.0 if not hit_df.empty else 0.0):.1f}%")

    st.subheader("Reason Type Distribution")
    st.bar_chart(filtered["reason_type"].value_counts())

    st.subheader("PnL by Symbol")
    pnl_by_symbol = filtered.groupby("symbol", as_index=False)["pnl_pct"].mean().set_index("symbol")
    st.bar_chart(pnl_by_symbol)

    st.subheader("Filtered Alerts")
    display_cols = [
        "trade_date",
        "symbol",
        "company_name",
        "sector",
        "direction",
        "percent_change",
        "reason_type",
        "confidence",
        "pnl_pct",
        "hit",
        "reason_provider",
        "reason",
        "evidence_urls",
    ]
    display_cols = [c for c in display_cols if c in filtered.columns]
    st.dataframe(filtered[display_cols].sort_values("trade_date", ascending=False), use_container_width=True)


if __name__ == "__main__":
    main()
