"""Tier 3 entry point: talk to Trillion by holding a key and speaking.

Run with:
    python -m trillion.voice_main

Wraps the exact same `Brain` and tool registry as the text CLI
(`trillion.main`) — voice only changes how a turn arrives (recorded
speech, transcribed by Deepgram) and leaves (spoken aloud by ElevenLabs).
The brain logic itself is never duplicated.

Known gap: playback is synchronous, so starting a new turn while
Trillion is still speaking (the "let me interrupt it" requirement) isn't
implemented yet — it needs to be exercised on real audio hardware to get
right, which this build environment doesn't have. The text CLI
(`trillion.main`) keeps working exactly as before for debugging anything
that isn't about audio itself.
"""

from __future__ import annotations

from dotenv import load_dotenv

from .audio_io import record_while_held
from .brain import Brain
from .cli_common import confirm_via_input, print_pending_notices
from .identity import NAME
from .provider import ProviderError
from .stt import STTError, transcribe
from .tts import TTSError, speak


def _print_tool_use(name: str, tool_input: dict, result: str) -> None:
    print(f"\n  [using {name}({tool_input}) -> {result}]")


def _confirm(tool_name: str, description: str, tool_input: dict) -> bool:
    """The confirmation gate for the voice CLI.

    Speaks the question aloud so you don't have to be looking at the
    screen, but takes the actual yes/no as typed input — deliberately,
    for a safety-critical decision a reliable typed answer beats another
    round of hold-to-talk and transcription that could be misheard.
    """
    try:
        speak(f"I want to {description} Should I go ahead?")
    except TTSError:
        pass  # the confirmation still works via the printed prompt below
    return confirm_via_input(tool_name, description, tool_input)


def main() -> None:
    load_dotenv()
    brain = Brain()

    print(f"{NAME} is ready. Hold SPACE and speak, release when done. Ctrl+C to quit.\n")
    print_pending_notices()

    while True:
        try:
            input("Press enter, then hold SPACE to talk...")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        print("Listening (hold SPACE)...")
        try:
            audio = record_while_held()
        except KeyboardInterrupt:
            print("\nGoodbye.")
            return
        except RuntimeError as exc:
            print(f"[couldn't record audio: {exc}]")
            continue

        try:
            user_text = transcribe(audio)
        except STTError as exc:
            print(f"[didn't catch that: {exc}]")
            continue

        if not user_text:
            print("[heard silence — try again]")
            continue

        # Printed so the ears and the brain can be told apart while debugging.
        print(f"You said: {user_text}")

        print(f"{NAME}: ", end="", flush=True)
        try:
            reply_text = brain.take_turn(
                user_text, on_tool_use=_print_tool_use, confirm=_confirm
            )
            print(reply_text)
        except ProviderError as exc:
            print(f"\n[trouble reaching {NAME} right now: {exc}]")
            continue

        try:
            speak(reply_text)
        except TTSError as exc:
            print(f"[couldn't speak the reply aloud: {exc}]")


if __name__ == "__main__":
    main()
