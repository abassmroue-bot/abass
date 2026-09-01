"""Thin seam around the model provider (Claude, via the Anthropic SDK).

Every other module talks to the model only through `send()`. If the
provider is ever swapped, this is the one file that should need to change.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

import anthropic

DEFAULT_MODEL = os.environ.get("TRILLION_MODEL", "claude-sonnet-5")
DEFAULT_MAX_TOKENS = int(os.environ.get("TRILLION_MAX_TOKENS", "1024"))


class ProviderError(Exception):
    """Raised whenever the model call can't be completed.

    Callers are expected to catch this, show me something readable, and
    keep the conversation loop alive — a network hiccup should never
    crash the assistant.
    """


@dataclass
class Reply:
    text: str
    stop_reason: str | None


def send(
    messages: list[dict],
    system_prompt: str,
    on_token: Callable[[str], None] | None = None,
) -> Reply:
    """Send a conversation to the model and return its full reply.

    `messages` is the running conversation (oldest first), each item a
    dict with "role" ("user" or "assistant") and "content" (plain text
    for now — tool-call content blocks arrive in Tier 2).

    If `on_token` is given, it's called with each chunk of reply text as
    it streams in, so a caller can print — or eventually speak — the
    reply before the whole thing has finished generating.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ProviderError(
            "ANTHROPIC_API_KEY is not set. Put it in your .env file "
            "(see .env.example) or export it in your shell."
        )

    client = anthropic.Anthropic(api_key=api_key)

    try:
        with client.messages.stream(
            model=DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for chunk in stream.text_stream:
                if on_token is not None:
                    on_token(chunk)
            final = stream.get_final_message()
    except anthropic.APIConnectionError as exc:
        raise ProviderError(f"couldn't reach the model provider ({exc})") from exc
    except anthropic.RateLimitError as exc:
        raise ProviderError(f"rate limited by the model provider ({exc})") from exc
    except anthropic.APIStatusError as exc:
        raise ProviderError(f"model provider returned an error ({exc})") from exc
    except anthropic.AnthropicError as exc:
        raise ProviderError(f"model provider error ({exc})") from exc

    text = "".join(
        block.text for block in final.content if getattr(block, "type", None) == "text"
    )
    return Reply(text=text, stop_reason=final.stop_reason)
