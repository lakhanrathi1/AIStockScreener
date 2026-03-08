from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List

from nsepython import nsefetch

logger = logging.getLogger(__name__)


INDEX_ENDPOINTS = [
    # NIFTY 50
    "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050",
    # NIFTY NEXT 50
    "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20NEXT%2050",
    # NIFTY MIDCAP 100
    "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20MIDCAP%20100",
    # NIFTY SMALLCAP 100
    "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20SMALLCAP%20100",
]


@dataclass
class StockMove:
    symbol: str
    company_name: str
    sector: str
    last_price: float
    prev_close: float
    percent_change: float
    direction: str  # "up" or "down"


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _company_name_from_row(row: dict) -> str:
    for key in (
        "companyName",
        "company_name",
        "name",
        "metaName",
        "displayName",
    ):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    meta = row.get("meta")
    if isinstance(meta, dict):
        for key in ("companyName", "name", "symbol"):
            value = meta.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    symbol = row.get("symbol")
    return str(symbol) if symbol else ""


def _sector_from_row(row: dict) -> str:
    for key in ("sector", "industry", "industryName"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    meta = row.get("meta")
    if isinstance(meta, dict):
        for key in ("industry", "sector", "industryName"):
            value = meta.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return "Unknown"


def fetch_index_snapshot() -> List[dict]:
    """
    Fetch a combined snapshot of all stocks in the configured NSE indices
    (NIFTY 50, NIFTY NEXT 50, NIFTY MIDCAP 100, NIFTY SMALLCAP 100).

    Results are de-duplicated by symbol if a stock appears in multiple indices.
    """
    combined: Dict[str, dict] = {}

    for url in INDEX_ENDPOINTS:
        logger.info("Fetching index snapshot: %s", url)
        payload = nsefetch(url)
        data = payload.get("data") or []
        logger.info("Fetched %d rows from endpoint", len(data))
        for row in data:
            symbol = row.get("symbol")
            if not symbol:
                continue
            combined[str(symbol)] = row

    return list(combined.values())


def compute_moves(
    min_abs_change: float,
    max_abs_change: float,
) -> List[StockMove]:
    """
    Compute stock moves for all symbols in the configured NSE indices and
    return those whose absolute percentage change lies between the configured
    bounds.
    """
    snapshot = fetch_index_snapshot()
    logger.info("Total unique stocks in snapshot: %d", len(snapshot))
    movers: List[StockMove] = []

    for row in snapshot:
        symbol = row.get("symbol")
        company_name = _company_name_from_row(row)
        sector = _sector_from_row(row)
        last_price = _safe_float(row.get("lastPrice"))
        prev_close = _safe_float(row.get("previousClose") or row.get("closePrice"))
        percent_change = _safe_float(row.get("pChange"))

        if prev_close <= 0 or symbol is None:
            continue

        if abs(percent_change) < min_abs_change or abs(percent_change) > max_abs_change:
            continue

        direction = "up" if percent_change >= 0 else "down"

        movers.append(
            StockMove(
                symbol=symbol,
                company_name=str(company_name),
                sector=sector,
                last_price=last_price,
                prev_close=prev_close,
                percent_change=percent_change,
                direction=direction,
            )
        )

    return movers


def select_top_movers(
    movers: Iterable[StockMove],
    max_per_side: int,
) -> List[StockMove]:
    """
    From a list of movers, return the top N per side (up/down) sorted by
    absolute percentage change descending.
    """
    sorted_movers = sorted(
        movers,
        key=lambda m: abs(m.percent_change),
        reverse=True,
    )

    up: List[StockMove] = []
    down: List[StockMove] = []

    for mover in sorted_movers:
        if mover.direction == "up" and len(up) < max_per_side:
            up.append(mover)
        elif mover.direction == "down" and len(down) < max_per_side:
            down.append(mover)

    return up + down
