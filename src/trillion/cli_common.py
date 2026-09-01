"""Small pieces shared by the text and voice CLIs (not the agent core
itself — see `brain.py` for that).
"""

from __future__ import annotations

from .heartbeat.config import load_heartbeat_config
from .heartbeat.notices import surface_pending


def print_pending_notices() -> None:
    """Catch up on anything the heartbeat noticed while this CLI was
    closed. Called once at startup by both `main.py` and `voice_main.py`
    so nothing the heartbeat surfaced while you were away is ever lost —
    it's shown here if it wasn't already, then still available via the
    list_notices tool until dismissed.
    """
    quiet_hours = load_heartbeat_config().quiet_hours
    notices = surface_pending(quiet_hours)
    for notice in notices:
        print(f"\n[{notice.level}] ({notice.check_name}) {notice.text}")
    if notices:
        print()
