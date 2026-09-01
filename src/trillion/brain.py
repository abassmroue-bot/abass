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
from .tools import ToolRegistry, build_registry
from .tools.memory import load_facts

# A safety valve, not a normal path: real conversations resolve in a
# handful of tool calls. If the model is stuck calling tools back-to-back
# past this, something's wrong — surface it instead of looping forever.
MAX_TOOL_ROUNDS = 8


class Brain:
    """Holds the running conversation and knows how to take one turn."""

    def __init__(self, tools: ToolRegistry | None = None) -> None:
        self.tools = tools if tools is not None else build_registry()
        self.history: list[dict] = []

    def _system_prompt(self) -> str:
        """Built fresh each turn so a fact remembered — or hand-edited in
        memory.md — takes effect on the very next turn, not just after a
        restart."""
        facts = [fact["text"] for fact in load_facts()]
        return build_system_prompt(tools_available=bool(self.tools.specs()), facts=facts)

    def take_turn(
        self,
        user_text: str,
        on_token: Callable[[str], None] | None = None,
        on_tool_use: Callable[[str, dict, str], None] | None = None,
    ) -> str:
        """Send `user_text` plus the running history to the model.

        The model may ask to call one or more tools before it's ready to
        answer; each is run through `self.tools` and its result fed back,
        for as many rounds as it takes. Returns the final reply text.

        On success, the whole exchange (including any tool calls) is
        appended to `self.history`. On failure, `provider.ProviderError`
        propagates to the caller and history is left exactly as it was —
        as if the turn never happened.

        `on_token` streams reply text as it's generated. `on_tool_use`,
        if given, is called after each tool finishes running, as
        `(tool_name, tool_input, result_text)` — handy for showing what
        the assistant is doing while it does it.
        """
        working_history = self.history + [{"role": "user", "content": user_text}]
        tool_specs = self.tools.specs() or None
        system_prompt = self._system_prompt()

        for _ in range(MAX_TOOL_ROUNDS):
            reply = provider.send(
                working_history, system_prompt, tools=tool_specs, on_token=on_token
            )
            working_history.append({"role": "assistant", "content": reply.content})

            if not reply.tool_uses:
                self.history = working_history
                return reply.text

            tool_results = []
            for call in reply.tool_uses:
                result_text = self.tools.run(call["name"], call["input"])
                if on_tool_use is not None:
                    on_tool_use(call["name"], call["input"], result_text)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call["id"],
                        "content": result_text,
                    }
                )
            working_history.append({"role": "user", "content": tool_results})

        raise provider.ProviderError(
            "gave up after too many tool-call rounds without a final reply"
        )
