"""A dedicated on/off switch for live automatic order placement.

Distinct from `trillion.kill_switch` (which pauses *all* proactive
heartbeat activity): this one gates specifically the money-spending path
the `gold_mt5_autotrade` heartbeat check can take. Off is the default —
autotrade being off is what the flag file's absence means, so a fresh
checkout, a wiped data dir, or a typo in `config.yaml` all fail toward
"do nothing" rather than toward "place real orders." Turning it on is
always a deliberate, one-time act taken outside of any conversation
(see the CLI below) — never a side effect of enabling the heartbeat
check itself, and never something a model conversation can flip on its
own. This is the carve-out AGENT.md's "never spend money without asking"
rule names explicitly for this feature.

Usage:
    python -m trillion.trading.autotrade_switch on
    python -m trillion.trading.autotrade_switch off
    python -m trillion.trading.autotrade_switch status
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _flag_path() -> Path:
    data_dir = Path(os.environ.get("TRILLION_DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "AUTOTRADE_ENABLED"


def is_autotrade_enabled() -> bool:
    return _flag_path().exists()


def enable_autotrade() -> None:
    stamp = datetime.now(timezone.utc).isoformat()
    _flag_path().write_text(f"enabled at {stamp}\n")


def disable_autotrade() -> None:
    _flag_path().unlink(missing_ok=True)


def _main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("on", "off", "status"):
        print("usage: python -m trillion.trading.autotrade_switch [on|off|status]")
        raise SystemExit(1)

    command = sys.argv[1]
    if command == "on":
        enable_autotrade()
        print(
            "MT5 autotrade ENABLED — the gold_mt5_autotrade heartbeat check will now place "
            "real live-account orders on signals, within the risk limits in config.yaml. "
            "Run 'python -m trillion.trading.autotrade_switch off' to stop it."
        )
    elif command == "off":
        disable_autotrade()
        print("MT5 autotrade disabled — no new orders will be placed.")
    else:
        print("Autotrade: ENABLED" if is_autotrade_enabled() else "Autotrade: disabled")


if __name__ == "__main__":
    _main()
