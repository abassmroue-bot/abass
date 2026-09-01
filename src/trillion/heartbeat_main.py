"""Tier 5 entry point: run the heartbeat loop.

Run with:
    python -m trillion.heartbeat_main

Separate from the conversation loop on purpose — it's meant to keep
running (e.g. as a systemd service on an always-on host) whether or not
you currently have trillion.main or trillion.voice_main open. Whatever it
finds waits in the notice inbox until you next open a conversation (see
`heartbeat.notices.surface_pending`, called at startup by both CLIs) or
ask "what's pending?" via the list_notices tool.
"""

from __future__ import annotations

from dotenv import load_dotenv

from .heartbeat.scheduler import Scheduler


def main() -> None:
    load_dotenv()
    Scheduler().run_forever()


if __name__ == "__main__":
    main()
