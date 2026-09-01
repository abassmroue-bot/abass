"""A plain, append-only audit trail: what the assistant did, and why.

When something surprises you, this is where you look. One JSON object
per line (`data/audit.log`) — structured enough to grep or parse,
readable enough to just open in a text editor.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _log_path() -> Path:
    data_dir = Path(os.environ.get("TRILLION_DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "audit.log"


def log_event(kind: str, **fields) -> None:
    """Append one event. Never raises — a logging failure must never be
    the reason the assistant itself breaks."""
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, **fields}
    try:
        with _log_path().open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        pass


def read_events() -> list[dict]:
    """Read the full audit trail back, oldest first. Used by tests and by
    anyone reviewing what happened — not on any hot path."""
    path = _log_path()
    if not path.exists():
        return []
    events = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
