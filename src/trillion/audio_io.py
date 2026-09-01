"""Push-to-talk audio capture and WAV encoding.

Hold a key to record, release to stop — this sidesteps voice-activity
detection entirely, which is what makes push-to-talk the reliable place
to start. Requires an actual microphone and, on some platforms,
permission to observe key events; see the Tier 3 notes in AGENT.md for
what to check if this doesn't work on your machine.
"""

from __future__ import annotations

import io
import wave
from collections.abc import Callable
from typing import Any

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000  # Hz — plenty for speech, keeps clips small
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2  # 16-bit PCM


def frames_to_wav_bytes(frames: list[np.ndarray], sample_rate: int = SAMPLE_RATE) -> bytes:
    """Pack recorded int16 audio frames into a WAV file, in memory."""
    if not frames:
        return b""
    audio = np.concatenate(frames, axis=0)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio.tobytes())
    return buffer.getvalue()


def record_while_held(
    key: Any = None,
    on_start: Callable[[], None] | None = None,
) -> bytes:
    """Record from the microphone while `key` is held down.

    Blocks until the key is pressed and then released, and returns the
    recording as WAV bytes. Raises RuntimeError if no input device is
    available (e.g. no microphone, or no permission to use it) or if
    there's no graphical session to observe the key press from (`pynput`
    needs one — a headless server has no keyboard to hold).
    """
    try:
        from pynput import keyboard  # imported lazily: needs a display/X server to load
    except ImportError as exc:
        raise RuntimeError(f"push-to-talk needs a graphical session ({exc})") from exc

    if key is None:
        key = keyboard.Key.space

    frames: list[np.ndarray] = []
    state = {"recording": False}

    def _audio_callback(indata, frame_count, time_info, status):
        if state["recording"]:
            frames.append(indata.copy())

    def _on_press(pressed_key):
        if pressed_key == key and not state["recording"]:
            state["recording"] = True
            if on_start is not None:
                on_start()

    def _on_release(released_key):
        if released_key == key and state["recording"]:
            state["recording"] = False
            return False  # stop the keyboard listener

    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", callback=_audio_callback
        )
    except Exception as exc:  # noqa: BLE001 - PortAudio raises several backend-specific errors
        raise RuntimeError(f"couldn't open a microphone ({exc})") from exc

    with stream:
        with keyboard.Listener(on_press=_on_press, on_release=_on_release) as listener:
            listener.join()

    return frames_to_wav_bytes(frames)
