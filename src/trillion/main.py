"""Tier 1/2 entry point: a plain-text conversation with Trillion.

Run with:
    python -m trillion.main

This is the assistant's brain and tools with no voice yet — a
conversation loop that remembers what was said earlier in the session and
can call tools (reminders, notes search) to actually do things. Keep this
working forever: it's the fastest way to debug every later change without
talking to your computer.
"""

from __future__ import annotations

from dotenv import load_dotenv

from .brain import Brain
from .identity import NAME
from .provider import ProviderError


def _print_tool_use(name: str, tool_input: dict, result: str) -> None:
    print(f"\n  [using {name}({tool_input}) -> {result}]")


def main() -> None:
    load_dotenv()
    brain = Brain()

    print(f"{NAME} is ready. Type a message, or /exit to quit.\n")

    while True:
        try:
            user_text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        if not user_text:
            continue
        if user_text in ("/exit", "/quit"):
            print("Goodbye.")
            return

        print(f"{NAME}: ", end="", flush=True)
        try:
            brain.take_turn(
                user_text,
                on_token=lambda chunk: print(chunk, end="", flush=True),
                on_tool_use=_print_tool_use,
            )
            print()
        except ProviderError as exc:
            print(f"\n[trouble reaching {NAME} right now: {exc}]")


if __name__ == "__main__":
    main()
