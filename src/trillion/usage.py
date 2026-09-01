"""A running tally of model token usage, so a runaway loop is visible
immediately rather than discovered later on a bill.

Deliberately tracks raw token counts rather than a dollar estimate —
pricing changes and varies by model, and a wrong dollar figure presented
as fact is worse than an honest token count.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _path() -> Path:
    data_dir = Path(os.environ.get("TRILLION_DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "usage.json"


def _load() -> dict:
    path = _path()
    if not path.exists():
        return {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"input_tokens": 0, "output_tokens": 0, "calls": 0}


def _save(totals: dict) -> None:
    _path().write_text(json.dumps(totals, indent=2))


def record_usage(input_tokens: int, output_tokens: int) -> dict:
    totals = _load()
    totals["input_tokens"] += input_tokens
    totals["output_tokens"] += output_tokens
    totals["calls"] += 1
    _save(totals)
    return totals


def current_totals() -> dict:
    return _load()
