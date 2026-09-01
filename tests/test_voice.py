from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import requests

from trillion import stt, tts
from trillion.audio_io import CHANNELS, SAMPLE_RATE, frames_to_wav_bytes


# --- tts.py ---------------------------------------------------------------


def test_synthesize_rejects_empty_text():
    with pytest.raises(tts.TTSError):
        tts.synthesize("   ")


def test_synthesize_requires_api_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(tts.TTSError, match="ELEVENLABS_API_KEY"):
        tts.synthesize("hello")


def test_synthesize_returns_joined_audio_bytes(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    fake_client = MagicMock()
    fake_client.text_to_speech.convert.return_value = [b"chunk1", b"chunk2"]

    with patch.object(tts, "ElevenLabs", return_value=fake_client):
        audio = tts.synthesize("hello there", voice_id="voice-123")

    assert audio == b"chunk1chunk2"
    fake_client.text_to_speech.convert.assert_called_once()
    _, kwargs = fake_client.text_to_speech.convert.call_args
    assert kwargs["voice_id"] == "voice-123"
    assert kwargs["text"] == "hello there"


def test_synthesize_wraps_provider_errors(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    fake_client = MagicMock()
    fake_client.text_to_speech.convert.side_effect = RuntimeError("provider down")

    with patch.object(tts, "ElevenLabs", return_value=fake_client):
        with pytest.raises(tts.TTSError, match="provider down"):
            tts.synthesize("hello")


# --- stt.py -----------------------------------------------------------------


def test_transcribe_rejects_empty_audio():
    with pytest.raises(stt.STTError):
        stt.transcribe(b"")


def test_transcribe_requires_api_key(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    with pytest.raises(stt.STTError, match="DEEPGRAM_API_KEY"):
        stt.transcribe(b"some audio bytes")


def test_transcribe_returns_transcript_on_success(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "results": {"channels": [{"alternatives": [{"transcript": "hello world"}]}]}
    }

    with patch.object(stt.requests, "post", return_value=fake_response) as fake_post:
        result = stt.transcribe(b"some audio bytes")

    assert result == "hello world"
    fake_post.assert_called_once()


def test_transcribe_wraps_network_errors(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")
    with patch.object(stt.requests, "post", side_effect=requests.RequestException("down")):
        with pytest.raises(stt.STTError, match="down"):
            stt.transcribe(b"some audio bytes")


def test_transcribe_raises_on_malformed_response(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"unexpected": "shape"}

    with patch.object(stt.requests, "post", return_value=fake_response):
        with pytest.raises(stt.STTError):
            stt.transcribe(b"some audio bytes")


# --- audio_io.py --------------------------------------------------------


def test_frames_to_wav_bytes_round_trips_audio_data():
    import wave
    import io

    frames = [
        np.array([[100], [200], [300]], dtype=np.int16),
        np.array([[400], [500]], dtype=np.int16),
    ]

    wav_bytes = frames_to_wav_bytes(frames)

    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        assert wav_file.getnchannels() == CHANNELS
        assert wav_file.getframerate() == SAMPLE_RATE
        assert wav_file.getnframes() == 5
        raw = wav_file.readframes(5)

    decoded = np.frombuffer(raw, dtype=np.int16)
    assert list(decoded) == [100, 200, 300, 400, 500]


def test_frames_to_wav_bytes_handles_no_audio():
    assert frames_to_wav_bytes([]) == b""
