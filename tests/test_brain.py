from unittest.mock import patch

from trillion import provider
from trillion.brain import Brain
from trillion.tools import Tool, ToolRegistry


def _text_reply(text: str) -> provider.Reply:
    return provider.Reply(content=[{"type": "text", "text": text}], stop_reason="end_turn")


def _empty_registry() -> ToolRegistry:
    return ToolRegistry()


def test_take_turn_uses_prior_history_and_appends_the_new_turn():
    brain = Brain(tools=_empty_registry())
    brain.history = [
        {"role": "user", "content": "my name is Alex"},
        {"role": "assistant", "content": [{"type": "text", "text": "Got it, Alex."}]},
    ]
    captured = {}

    def fake_send(messages, system_prompt, tools=None, on_token=None):
        captured["messages"] = list(messages)
        return _text_reply("Sure thing.")

    with patch.object(provider, "send", side_effect=fake_send):
        reply = brain.take_turn("what's my name?")

    assert reply == "Sure thing."
    # the model saw the earlier turns, not just the new one
    assert captured["messages"][0]["content"] == "my name is Alex"
    assert captured["messages"][-1] == {"role": "user", "content": "what's my name?"}
    # the new turn is now part of history for next time
    assert brain.history[-2] == {"role": "user", "content": "what's my name?"}
    assert brain.history[-1]["content"][0]["text"] == "Sure thing."


def test_take_turn_leaves_history_untouched_on_provider_failure():
    brain = Brain(tools=_empty_registry())
    brain.history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": [{"type": "text", "text": "hello"}]},
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
    brain = Brain(tools=_empty_registry())
    chunks = []

    def fake_send(messages, system_prompt, tools=None, on_token=None):
        for piece in ["Hel", "lo!"]:
            on_token(piece)
        return _text_reply("Hello!")

    with patch.object(provider, "send", side_effect=fake_send):
        brain.take_turn("hi", on_token=chunks.append)

    assert chunks == ["Hel", "lo!"]


def test_take_turn_runs_a_tool_and_feeds_the_result_back():
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="add_numbers",
            description="Add two numbers.",
            input_schema={
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"],
            },
            handler=lambda inp: str(inp["a"] + inp["b"]),
        )
    )
    brain = Brain(tools=registry)

    tool_use_reply = provider.Reply(
        content=[
            {
                "type": "tool_use",
                "id": "call_1",
                "name": "add_numbers",
                "input": {"a": 2, "b": 3},
            }
        ],
        stop_reason="tool_use",
    )
    final_reply = _text_reply("2 + 3 is 5.")

    responses = [tool_use_reply, final_reply]
    captured_second_call = {}

    def fake_send(messages, system_prompt, tools=None, on_token=None):
        response = responses.pop(0)
        if not responses:
            captured_second_call["messages"] = list(messages)
        return response

    tool_use_events = []

    with patch.object(provider, "send", side_effect=fake_send):
        reply = brain.take_turn(
            "what's 2 + 3?",
            on_tool_use=lambda name, inp, result: tool_use_events.append((name, inp, result)),
        )

    assert reply == "2 + 3 is 5."
    assert tool_use_events == [("add_numbers", {"a": 2, "b": 3}, "5")]

    # the tool result was fed back to the model as a tool_result block
    tool_result_message = captured_second_call["messages"][-1]
    assert tool_result_message["role"] == "user"
    assert tool_result_message["content"] == [
        {"type": "tool_result", "tool_use_id": "call_1", "content": "5"}
    ]

    # the full round trip (including the tool call and its result) lands in history
    assert brain.history[-3]["content"][0]["type"] == "tool_use"
    assert brain.history[-2]["content"][0]["type"] == "tool_result"
    assert brain.history[-1]["content"][0]["text"] == "2 + 3 is 5."


def test_take_turn_gives_up_after_too_many_tool_rounds():
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="loop_forever",
            description="A tool that always asks to be called again.",
            input_schema={"type": "object", "properties": {}},
            handler=lambda inp: "ok",
        )
    )
    brain = Brain(tools=registry)

    def fake_send(messages, system_prompt, tools=None, on_token=None):
        return provider.Reply(
            content=[{"type": "tool_use", "id": "x", "name": "loop_forever", "input": {}}],
            stop_reason="tool_use",
        )

    with patch.object(provider, "send", side_effect=fake_send):
        try:
            brain.take_turn("go")
            assert False, "expected ProviderError after too many rounds"
        except provider.ProviderError:
            pass
