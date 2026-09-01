"""One obvious way to pause all proactive behavior without tearing
anything down.

This only affects the heartbeat (`heartbeat.scheduler.Scheduler.tick`) —
the conversation loop is untouched, so you can always still talk to the
assistant while it's paused.

Usage:
    python -m trillion.kill_switch pause ["reason"]
    python -m trillion.kill_switch resume
    python -m trillion.kill_switch status
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _flag_path() -> Path:
    data_dir = Path(os.environ.get("TRILLION_DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "PAUSED"


def is_paused() -> bool:
    return _flag_path().exists()


def pause(reason: str = "") -> None:
    stamp = datetime.now(timezone.utc).isoformat()
    _flag_path().write_text(f"{stamp} {reason}".rstrip() + "\n")


def resume() -> None:
    _flag_path().unlink(missing_ok=True)


def _main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("pause", "resume", "status"):
        print("usage: python -m trillion.kill_switch [pause [reason] | resume | status]")
        raise SystemExit(1)

    command = sys.argv[1]
    if command == "pause":
        pause(" ".join(sys.argv[2:]))
        print(
            "Heartbeat paused — the conversation still works normally. "
            "Run 'python -m trillion.kill_switch resume' to re-enable it."
        )
    elif command == "resume":
        resume()
        print("Heartbeat resumed.")
    else:
        print(f"Paused: {_flag_path().read_text().strip()}" if is_paused() else "Not paused.")


if __name__ == "__main__":
    _main()
