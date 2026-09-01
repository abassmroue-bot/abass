"""Thin seam around text-to-speech (the reference build uses ElevenLabs).

Every other module reaches speech synthesis only through `synthesize()`
and `speak()`. If the voice provider is ever swapped, this is the one
file that should need to change.
"""

from __future__ import annotations

import os

from elevenlabs import ElevenLabs

# ElevenLabs' well-known "Rachel" premade voice — a reasonable default
# until a real voice choice is set (Tier 6 config). Override with
# ELEVENLABS_VOICE_ID once you've picked one you like.
DEFAULT_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
DEFAULT_MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")


class TTSError(Exception):
    """Raised whenever speech synthesis can't be completed.

    Callers should catch this and keep going — e.g. fall back to printed
    text — rather than let a voice-provider hiccup crash the assistant.
    """


def _client() -> ElevenLabs:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise TTSError(
            "ELEVENLABS_API_KEY is not set. Put it in your .env file "
            "(see .env.example) or export it in your shell."
        )
    return ElevenLabs(api_key=api_key)


def synthesize(text: str, voice_id: str | None = None) -> bytes:
    """Turn `text` into speech and return the full audio (mp3) as bytes.

    This is the piece that's easy to verify without speakers: the bytes
    it returns can be written to a file and played back by a human, or
    inspected for a non-trivial size, without any audio hardware here.
    """
    if not text.strip():
        raise TTSError("nothing to say — text was empty")

    client = _client()
    try:
        chunks = client.text_to_speech.convert(
            voice_id=voice_id or DEFAULT_VOICE_ID,
            model_id=DEFAULT_MODEL_ID,
            text=text,
        )
        return b"".join(chunks)
    except Exception as exc:  # noqa: BLE001 - the SDK raises several error types
        raise TTSError(f"couldn't reach the voice provider ({exc})") from exc


def speak(text: str, voice_id: str | None = None) -> None:
    """Synthesize `text` and play it out loud.

    Falls back to a clear message (rather than crashing) when there's no
    audio output available in the current environment — e.g. a headless
    server with no speakers and no media player installed.
    """
    from elevenlabs import play as _play  # imported lazily: pulls in an audio backend

    audio = synthesize(text, voice_id=voice_id)
    try:
        _play(audio)
    except Exception as exc:  # noqa: BLE001 - playback backends fail in many different ways
        raise TTSError(f"synthesized the reply but couldn't play it aloud ({exc})") from exc
