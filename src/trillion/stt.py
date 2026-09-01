"""Thin seam around speech-to-text (the reference build uses Deepgram).

Every other module reaches transcription only through `transcribe()`. If
the transcriber is ever swapped, this is the one file that should need to
change.
"""

from __future__ import annotations

import os

import requests

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
DEFAULT_MODEL = os.environ.get("DEEPGRAM_MODEL", "nova-2")


class STTError(Exception):
    """Raised whenever transcription can't be completed.

    Callers should catch this and tell me plainly ("didn't catch that")
    rather than let a network hiccup crash the assistant mid-conversation.
    """


def transcribe(audio_bytes: bytes, mimetype: str = "audio/wav") -> str:
    """Send recorded audio to Deepgram and return the transcribed text.

    `audio_bytes` is a single, complete recording (push-to-talk captures
    the whole clip before this is called — no need to stream chunks in).
    """
    if not audio_bytes:
        raise STTError("no audio to transcribe — the recording was empty")

    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        raise STTError(
            "DEEPGRAM_API_KEY is not set. Put it in your .env file "
            "(see .env.example) or export it in your shell."
        )

    try:
        response = requests.post(
            DEEPGRAM_URL,
            params={"model": DEFAULT_MODEL, "smart_format": "true"},
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": mimetype,
            },
            data=audio_bytes,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise STTError(f"couldn't reach the transcription provider ({exc})") from exc

    try:
        result = response.json()
        transcript = result["results"]["channels"][0]["alternatives"][0]["transcript"]
    except (KeyError, IndexError, ValueError) as exc:
        raise STTError(f"got an unexpected response from the transcription provider ({exc})") from exc

    return transcript.strip()
