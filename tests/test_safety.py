from unittest.mock import patch

from trillion import audit, config as app_config, provider, usage
from trillion.brain import Brain
from trillion.kill_switch import is_paused, pause, resume
from trillion.tools import Tool, ToolRegistry
from trillion.tools.memory import remember_fact


def _text_reply(text: str, usage_tokens: tuple[int, int] | None = None) -> provider.Reply:
    reply_usage = None
    if usage_tokens is not None:
        reply_usage = {"input_tokens": usage_tokens[0], "output_tokens": usage_tokens[1]}
    return provider.Reply(
        content=[{"type": "text", "text": text}], stop_reason="end_turn", usage=reply_usage
    )


def _tool_use_reply(call_id: str, name: str, tool_input: dict) -> provider.Reply:
    return provider.Reply(
        content=[{"type": "tool_use", "id": call_id, "name": name, "input": tool_input}],
        stop_reason="tool_use",
    )


def _registry_with_gated_tool(handler_result: str = "done") -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="delete_thing",
            description="Permanently delete the user's thing.",
            input_schema={"type": "object", "properties": {}},
            handler=lambda inp: handler_result,
            requires_confirmation=True,
        )
    )
    return registry


# --- config.py ---------------------------------------------------------


def test_get_model_name_env_wins_over_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("model:\n  name: from-config\n")
    monkeypatch.setenv("TRILLION_MODEL", "from-env")
    assert app_config.get_model_name(str(config_file)) == "from-env"


def test_get_model_name_falls_back_to_config_then_default(tmp_path, monkeypatch):
    monkeypatch.delenv("TRILLION_MODEL", raising=False)
    config_file = tmp_path / "config.yaml"
    config_file.write_text("model:\n  name: from-config\n")
    assert app_config.get_model_name(str(config_file)) == "from-config"
    assert app_config.get_model_name(str(tmp_path / "missing.yaml")) == "claude-sonnet-5"


def test_get_confirmation_required_tools_reads_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("tools:\n  require_confirmation:\n    - complete_reminder\n")
    assert app_config.get_confirmation_required_tools(str(config_file)) == {"complete_reminder"}


def test_get_confirmation_required_tools_empty_when_missing(tmp_path):
    assert app_config.get_confirmation_required_tools(str(tmp_path / "missing.yaml")) == set()


# --- ToolRegistry.requires_confirmation -------------------------------------


def test_requires_confirmation_true_when_tool_declares_it():
    registry = _registry_with_gated_tool()
    assert registry.requires_confirmation("delete_thing") is True


def test_requires_confirmation_false_by_default():
    registry = ToolRegistry()
    registry.register(
        Tool(name="harmless", description="d", input_schema={}, handler=lambda inp: "ok")
    )
    assert registry.requires_confirmation("harmless") is False


def test_requires_confirmation_widened_by_config(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_CONFIG_PATH", str(tmp_path / "config.yaml"))
    (tmp_path / "config.yaml").write_text("tools:\n  require_confirmation:\n    - harmless\n")
    registry = ToolRegistry()
    registry.register(
        Tool(name="harmless", description="d", input_schema={}, handler=lambda inp: "ok")
    )
    assert registry.requires_confirmation("harmless") is True


def test_requires_confirmation_false_for_unknown_tool():
    registry = ToolRegistry()
    assert registry.requires_confirmation("nope") is False


# --- Brain: the confirmation gate --------------------------------------


def test_gated_tool_runs_when_confirm_grants_it():
    registry = _registry_with_gated_tool(handler_result="deleted!")
    brain = Brain(tools=registry)
    confirmations = []

    def confirm(name, description, tool_input):
        confirmations.append((name, description, tool_input))
        return True

    responses = [_tool_use_reply("c1", "delete_thing", {}), _text_reply("Done.")]

    def fake_send(messages, system_prompt, tools=None, on_token=None):
        return responses.pop(0)

    with patch.object(provider, "send", side_effect=fake_send):
        reply = brain.take_turn("delete my thing", confirm=confirm)

    assert reply == "Done."
    assert len(confirmations) == 1
    assert confirmations[0][0] == "delete_thing"


def test_gated_tool_does_not_run_when_confirm_declines():
    ran = {"called": False}
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="delete_thing",
            description="Permanently delete the user's thing.",
            input_schema={"type": "object", "properties": {}},
            handler=lambda inp: ran.update(called=True) or "deleted!",
            requires_confirmation=True,
        )
    )
    brain = Brain(tools=registry)

    responses = [_tool_use_reply("c1", "delete_thing", {}), _text_reply("Okay, I won't.")]

    def fake_send(messages, system_prompt, tools=None, on_token=None):
        return responses.pop(0)

    with patch.object(provider, "send", side_effect=fake_send):
        reply = brain.take_turn("delete my thing", confirm=lambda *a: False)

    assert reply == "Okay, I won't."
    assert ran["called"] is False  # the handler never actually ran


def test_gated_tool_defaults_to_declined_when_no_confirm_given():
    ran = {"called": False}
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="delete_thing",
            description="d",
            input_schema={"type": "object", "properties": {}},
            handler=lambda inp: ran.update(called=True) or "deleted!",
            requires_confirmation=True,
        )
    )
    brain = Brain(tools=registry)

    responses = [_tool_use_reply("c1", "delete_thing", {}), _text_reply("Okay.")]

    def fake_send(messages, system_prompt, tools=None, on_token=None):
        return responses.pop(0)

    with patch.object(provider, "send", side_effect=fake_send):
        brain.take_turn("delete my thing")  # no confirm= passed at all

    assert ran["called"] is False


def test_confirmation_is_asked_again_every_time_not_cached():
    registry = _registry_with_gated_tool()
    brain = Brain(tools=registry)
    call_count = {"n": 0}

    def confirm(name, description, tool_input):
        call_count["n"] += 1
        return True

    # two separate turns, each with its own tool call
    for _ in range(2):
        responses = [_tool_use_reply("c1", "delete_thing", {}), _text_reply("Done.")]

        def fake_send(messages, system_prompt, tools=None, on_token=None):
            return responses.pop(0)

        with patch.object(provider, "send", side_effect=fake_send):
            brain.take_turn("delete it", confirm=confirm)

    assert call_count["n"] == 2  # asked fresh both times, never remembered


def test_forget_fact_is_gated_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    remember_fact({"text": "some fact"})
    from trillion.tools import build_registry

    registry = build_registry()
    assert registry.requires_confirmation("forget_fact") is True


# --- audit.py ----------------------------------------------------------


def test_audit_log_records_and_reads_back_events(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    audit.log_event("tool_call", tool="add_reminder", input={"text": "x"}, result="ok")
    audit.log_event("confirmation", tool="forget_fact", input={"id": "abc"}, granted=False)

    events = audit.read_events()
    assert len(events) == 2
    assert events[0]["kind"] == "tool_call"
    assert events[1]["granted"] is False


def test_audit_log_never_raises_on_bad_directory(monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", "/nonexistent/definitely/not/writable/path")
    audit.log_event("tool_call", tool="x")  # must not raise


def test_brain_logs_tool_calls_and_confirmations_to_the_audit_trail(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    registry = _registry_with_gated_tool()
    brain = Brain(tools=registry)

    responses = [_tool_use_reply("c1", "delete_thing", {}), _text_reply("Done.")]

    def fake_send(messages, system_prompt, tools=None, on_token=None):
        return responses.pop(0)

    with patch.object(provider, "send", side_effect=fake_send):
        brain.take_turn("delete it", confirm=lambda *a: True)

    events = audit.read_events()
    kinds = [e["kind"] for e in events]
    assert "confirmation" in kinds
    assert "tool_call" in kinds


# --- usage.py ------------------------------------------------------------


def test_usage_tally_accumulates(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    usage.record_usage(100, 50)
    usage.record_usage(20, 10)
    totals = usage.current_totals()
    assert totals == {"input_tokens": 120, "output_tokens": 60, "calls": 2}


def test_brain_records_usage_from_provider_replies(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    brain = Brain(tools=ToolRegistry())

    def fake_send(messages, system_prompt, tools=None, on_token=None):
        return _text_reply("hi", usage_tokens=(42, 7))

    with patch.object(provider, "send", side_effect=fake_send):
        brain.take_turn("hello")

    assert usage.current_totals()["input_tokens"] == 42
    assert usage.current_totals()["output_tokens"] == 7


# --- kill_switch.py ------------------------------------------------------


def test_kill_switch_pause_and_resume(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    assert is_paused() is False
    pause("testing")
    assert is_paused() is True
    resume()
    assert is_paused() is False


def test_paused_heartbeat_skips_all_checks_but_conversation_still_works(tmp_path, monkeypatch):
    from datetime import datetime, time as dt_time

    from trillion.heartbeat.config import CheckConfig, HeartbeatConfig, QuietHours
    from trillion.heartbeat.notices import list_notices
    from trillion.heartbeat.scheduler import Scheduler
    from trillion.tools.reminders import add_reminder

    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    add_reminder({"text": "buy milk"})
    pause("testing")

    config = HeartbeatConfig(
        poll_interval_seconds=1,
        quiet_hours=QuietHours(start=dt_time(22, 0), end=dt_time(7, 0)),
        checks=[CheckConfig(name="open_reminders_digest", interval_seconds=1, params={})],
    )
    Scheduler(config).tick(now=datetime(2026, 1, 1, 12, 0))
    assert list_notices() == []  # nothing ran while paused

    # meanwhile the conversation loop is completely unaffected by the pause
    brain = Brain(tools=ToolRegistry())

    def fake_send(messages, system_prompt, tools=None, on_token=None):
        return _text_reply("still here")

    with patch.object(provider, "send", side_effect=fake_send):
        assert brain.take_turn("are you there?") == "still here"

    resume()
    Scheduler(config).tick(now=datetime(2026, 1, 1, 12, 0, 2))
    assert len(list_notices()) == 1  # resumed, now it runs
