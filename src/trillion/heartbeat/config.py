"""Loads heartbeat configuration from a plain YAML file.

What to check, how often, and quiet hours are things you'll tune
constantly — keeping them here means every change is a one-line edit,
never a code change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time as dt_time
from pathlib import Path

import yaml

def _default_config_path() -> str:
    # Read fresh each call, not once at import — so setting the env var
    # later (including in a test) is actually honored.
    return os.environ.get("TRILLION_CONFIG_PATH", "config.yaml")


@dataclass
class QuietHours:
    start: dt_time
    end: dt_time


@dataclass
class CheckConfig:
    name: str
    enabled: bool = True
    interval_seconds: int = 300
    params: dict = field(default_factory=dict)


@dataclass
class HeartbeatConfig:
    poll_interval_seconds: int
    quiet_hours: QuietHours
    checks: list[CheckConfig]


def _parse_time(value: str) -> dt_time:
    hour, minute = value.split(":")
    return dt_time(hour=int(hour), minute=int(minute))


def load_heartbeat_config(path: str | None = None) -> HeartbeatConfig:
    """Load `config.yaml`'s `heartbeat:` section.

    Missing file or missing keys fall back to sensible defaults (quiet,
    with no checks enabled) rather than raising — a heartbeat that can't
    find its config should do nothing, not crash the assistant.
    """
    config_path = Path(path or _default_config_path())
    if not config_path.exists():
        return HeartbeatConfig(
            poll_interval_seconds=30,
            quiet_hours=QuietHours(start=dt_time(22, 0), end=dt_time(7, 0)),
            checks=[],
        )

    raw = yaml.safe_load(config_path.read_text()) or {}
    hb = raw.get("heartbeat") or {}
    quiet_raw = hb.get("quiet_hours") or {"start": "22:00", "end": "07:00"}

    checks = [
        CheckConfig(
            name=c["name"],
            enabled=c.get("enabled", True),
            interval_seconds=c.get("interval_seconds", 300),
            params=c.get("params") or {},
        )
        for c in (hb.get("checks") or [])
    ]

    return HeartbeatConfig(
        poll_interval_seconds=hb.get("poll_interval_seconds", 30),
        quiet_hours=QuietHours(
            start=_parse_time(quiet_raw["start"]), end=_parse_time(quiet_raw["end"])
        ),
        checks=checks,
    )
