"""The scheduler: runs each enabled check on its own interval.

Single-threaded and sequential on purpose — a check can't overlap
itself (Python can't call it again until the current call returns), and
the tradeoff (a slow check delays other checks' turn that tick) is a
simple, acceptable one for a background loop like this. State is
persisted to disk so a restart doesn't reset every timer or refire
everything at once.
"""

from __future__ import annotations

import hashlib
import json
import os
import time as time_module
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .checks import CHECKS
from .config import HeartbeatConfig, load_heartbeat_config
from .notices import add_notice


def _state_path() -> Path:
    data_dir = Path(os.environ.get("TRILLION_DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "heartbeat_state.json"


def _load_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _save_state(state: dict) -> None:
    _state_path().write_text(json.dumps(state, indent=2))


class Scheduler:
    def __init__(self, config: HeartbeatConfig | None = None) -> None:
        self.config = config if config is not None else load_heartbeat_config()
        self.state = _load_state()

    def tick(self, now: datetime | None = None) -> None:
        """Run whatever's due, then persist. Safe to call as often as you
        like — a check that isn't due yet, or is disabled, is a no-op."""
        now = now or datetime.now(timezone.utc)
        changed = False

        for check_config in self.config.checks:
            if not check_config.enabled:
                continue
            check_fn = CHECKS.get(check_config.name)
            if check_fn is None:
                continue  # config names a check we don't have — ignore, don't crash

            entry = self.state.get(check_config.name) or {}
            next_due_raw = entry.get("next_due")
            next_due = datetime.fromisoformat(next_due_raw) if next_due_raw else now
            if next_due > now:
                continue

            try:
                result = check_fn(check_config.params)
            except Exception as exc:  # noqa: BLE001 - one bad check must never take the loop down
                result = None
                print(f"[heartbeat] check {check_config.name!r} failed: {exc}")

            result_hash = None
            if result is not None:
                result_hash = hashlib.sha256(result.text.encode()).hexdigest()
                # Only notify when the finding actually changed since last
                # time — otherwise an unresolved condition would re-notify
                # on every tick, which is exactly the "crying wolf" this
                # build is meant to avoid.
                if result_hash != entry.get("last_result_hash"):
                    add_notice(check_config.name, result.level, result.text)

            self.state[check_config.name] = {
                "next_due": (now + timedelta(seconds=check_config.interval_seconds)).isoformat(),
                "last_result_hash": result_hash,
            }
            changed = True

        if changed:
            _save_state(self.state)

    def run_forever(self) -> None:
        print("[heartbeat] running — Ctrl+C to stop")
        try:
            while True:
                self.tick()
                time_module.sleep(self.config.poll_interval_seconds)
        except KeyboardInterrupt:
            print("\n[heartbeat] stopped")
