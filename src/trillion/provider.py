"""Thin seam around the model provider (Claude, via the Anthropic SDK).

Every other module talks to the model only through `send()`. If the
provider is ever swapped, this is the one file that should need to change.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

import anthropic

from . import config as app_config

DEFAULT_MAX_TOKENS = int(os.environ.get("TRILLION_MAX_TOKENS", "1024"))


class ProviderError(Exception):
    """Raised whenever the model call can't be completed.

    Callers are expected to catch this, show me something readable, and
    keep the conversation loop alive — a network hiccup should never
    crash the assistant.
    """


@dataclass
class Reply:
    """A model reply, as plain-dict content blocks (text and/or tool_use).

    Kept as plain dicts rather than raw SDK objects so the rest of the
    harness (and its tests) never need to import `anthropic` and so these
    blocks can be fed straight back into the next `send()` call as-is.
    """

    content: list[dict]
    stop_reason: str | None
    usage: dict | None = None  # {"input_tokens": int, "output_tokens": int}, when known

    @property
    def text(self) -> str:
        return "".join(b["text"] for b in self.content if b.get("type") == "text")

    @property
    def tool_uses(self) -> list[dict]:
        return [b for b in self.content if b.get("type") == "tool_use"]


def _serialize_content(blocks) -> list[dict]:
    serialized: list[dict] = []
    for block in blocks:
        if block.type == "text":
            serialized.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            serialized.append(
                {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
            )
    return serialized


def send(
    messages: list[dict],
    system_prompt: str,
    tools: list[dict] | None = None,
    on_token: Callable[[str], None] | None = None,
) -> Reply:
    """Send a conversation to the model and return its full reply.

    `messages` is the running conversation (oldest first). Each item is a
    dict with "role" ("user" or "assistant") and "content" — either plain
    text, or a list of content blocks (text / tool_use / tool_result) once
    tools are in play.

    `tools`, when given, is a list of tool specs in the provider's format
    (see `trillion.tools.registry.Tool.spec`); the model may respond with
    one or more `tool_use` blocks instead of (or alongside) text.

    If `on_token` is given, it's called with each chunk of reply *text* as
    it streams in (tool-call blocks aren't streamed token-by-token), so a
    caller can print — or eventually speak — the reply before the whole
    thing has finished generating.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ProviderError(
            "ANTHROPIC_API_KEY is not set. Put it in your .env file "
            "(see .env.example) or export it in your shell."
        )

    client = anthropic.Anthropic(api_key=api_key)

    kwargs: dict = dict(
        model=app_config.get_model_name(),
        max_tokens=DEFAULT_MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )
    if tools:
        kwargs["tools"] = tools

    try:
        with client.messages.stream(**kwargs) as stream:
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

    usage = None
    if getattr(final, "usage", None) is not None:
        usage = {
            "input_tokens": final.usage.input_tokens,
            "output_tokens": final.usage.output_tokens,
        }

    return Reply(
        content=_serialize_content(final.content), stop_reason=final.stop_reason, usage=usage
    )
