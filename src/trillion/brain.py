"""The agent core: one shared conversation loop.

Every way of talking to Trillion — typed text now, voice in Tier 3, a
heartbeat-initiated check in Tier 5 — is meant to funnel through this same
`Brain`. Nothing in here knows or cares whether a turn came from a
keyboard, a microphone, or a scheduled check; that's the whole point.
"""

from __future__ import annotations

from collections.abc import Callable

from . import provider
from .identity import build_system_prompt


class Brain:
    """Holds the running conversation and knows how to take one turn."""

    def __init__(self) -> None:
        self.system_prompt = build_system_prompt()
        self.history: list[dict] = []

    def take_turn(
        self,
        user_text: str,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """Send `user_text` plus the running history to the model.

        Returns the assistant's reply text. On success, both the user's
        turn and the assistant's reply are appended to `self.history`. On
        failure, `provider.ProviderError` propagates to the caller and
        history is left exactly as it was — as if the turn never
        happened — so a retry doesn't duplicate anything.
        """
        turn_messages = self.history + [{"role": "user", "content": user_text}]
        reply = provider.send(turn_messages, self.system_prompt, on_token=on_token)

        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply.text})
        return reply.text
