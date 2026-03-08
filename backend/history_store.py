from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import pandas as pd
from pandas.errors import EmptyDataError


def _history_path() -> Path:
    return Path(os.getenv("ALERT_HISTORY_PATH", "data/alerts_history.csv"))


def append_alert_rows(rows: Iterable[dict]) -> Path:
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    incoming = pd.DataFrame(list(rows))
    if incoming.empty:
        return path

    if path.exists():
        try:
            existing = pd.read_csv(path)
            if existing.empty and len(existing.columns) == 0:
                combined = incoming
            else:
                combined = pd.concat([existing, incoming], ignore_index=True)
        except (EmptyDataError, FileNotFoundError):
            combined = incoming
    else:
        combined = incoming

    combined.to_csv(path, index=False)
    return path
