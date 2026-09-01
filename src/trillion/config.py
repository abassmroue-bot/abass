"""Trillion-wide settings loaded from config.yaml (not heartbeat-specific
— see `heartbeat/config.py` for that).

Precedence: an environment variable always wins over the config file,
which wins over the hardcoded fallback here. That's what lets you tune
things — the model name, which tools need confirmation — without ever
touching code.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

DEFAULT_MODEL_NAME = "claude-sonnet-5"


def _default_config_path() -> str:
    # Read fresh each call, not once at import — so setting the env var
    # later (including in a test) is actually honored.
    return os.environ.get("TRILLION_CONFIG_PATH", "config.yaml")


def _raw_config(path: str | None = None) -> dict:
    config_path = Path(path or _default_config_path())
    if not config_path.exists():
        return {}
    return yaml.safe_load(config_path.read_text()) or {}


def get_model_name(path: str | None = None) -> str:
    env_value = os.environ.get("TRILLION_MODEL")
    if env_value:
        return env_value
    raw = _raw_config(path)
    return (raw.get("model") or {}).get("name", DEFAULT_MODEL_NAME)


def get_confirmation_required_tools(path: str | None = None) -> set[str]:
    """Tool names that must go through the confirmation gate.

    This is additive on top of whatever a tool already declares in code
    (`Tool.requires_confirmation=True`) — config can widen the gate to
    cover more tools, but can't be used to quietly narrow it below what
    the tool's own author decided was unsafe to run unattended.
    """
    raw = _raw_config(path)
    configured = (raw.get("tools") or {}).get("require_confirmation") or []
    return set(configured)
