from unittest.mock import patch

from trillion import provider
from trillion.brain import Brain


def test_take_turn_uses_prior_history_and_appends_the_new_turn():
    brain = Brain()
    brain.history = [
        {"role": "user", "content": "my name is Alex"},
        {"role": "assistant", "content": "Got it, Alex."},
    ]
    captured = {}

    def fake_send(messages, system_prompt, on_token=None):
        captured["messages"] = messages
        return provider.Reply(text="Sure thing.", stop_reason="end_turn")

    with patch.object(provider, "send", side_effect=fake_send):
        reply = brain.take_turn("what's my name?")

    assert reply == "Sure thing."
    # the model saw the earlier turns, not just the new one
    assert captured["messages"][0]["content"] == "my name is Alex"
    assert captured["messages"][-1] == {"role": "user", "content": "what's my name?"}
    # the new turn is now part of history for next time
    assert brain.history[-2] == {"role": "user", "content": "what's my name?"}
    assert brain.history[-1] == {"role": "assistant", "content": "Sure thing."}


def test_take_turn_leaves_history_untouched_on_provider_failure():
    brain = Brain()
    brain.history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    history_before = list(brain.history)

    def fake_send(*args, **kwargs):
        raise provider.ProviderError("network down")

    with patch.object(provider, "send", side_effect=fake_send):
        try:
            brain.take_turn("are you there?")
            assert False, "expected ProviderError to propagate"
        except provider.ProviderError:
            pass

    assert brain.history == history_before


def test_take_turn_streams_tokens_via_on_token():
    brain = Brain()
    chunks = []

    def fake_send(messages, system_prompt, on_token=None):
        for piece in ["Hel", "lo!"]:
            on_token(piece)
        return provider.Reply(text="Hello!", stop_reason="end_turn")

    with patch.object(provider, "send", side_effect=fake_send):
        brain.take_turn("hi", on_token=chunks.append)

    assert chunks == ["Hel", "lo!"]
