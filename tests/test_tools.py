import pytest

from trillion.tools import Tool, ToolRegistry
from trillion.tools import notes as notes_module
from trillion.tools import reminders as reminders_module


def test_registry_runs_a_registered_tool():
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="shout",
            description="Uppercase some text.",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
            handler=lambda inp: inp["text"].upper(),
        )
    )
    assert registry.run("shout", {"text": "hi"}) == "HI"


def test_registry_reports_unknown_tool_without_raising():
    registry = ToolRegistry()
    assert "no such tool" in registry.run("nope", {})


def test_registry_reports_handler_errors_without_raising():
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="boom",
            description="Always fails.",
            input_schema={"type": "object", "properties": {}},
            handler=lambda inp: 1 / 0,
        )
    )
    result = registry.run("boom", {})
    assert result.startswith("error: boom failed")


def test_registry_rejects_duplicate_names():
    registry = ToolRegistry()
    tool = Tool(name="dup", description="d", input_schema={}, handler=lambda inp: "x")
    registry.register(tool)
    with pytest.raises(ValueError):
        registry.register(tool)


def test_add_list_and_complete_reminder_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))

    add_result = reminders_module.add_reminder({"text": "buy milk", "due": "tomorrow"})
    assert "buy milk" in add_result
    reminder_id = add_result.split("[")[1].split("]")[0]

    listing = reminders_module.list_reminders({})
    assert "buy milk" in listing
    assert "(due tomorrow)" in listing

    complete_result = reminders_module.complete_reminder({"id": reminder_id})
    assert "Marked" in complete_result

    assert reminders_module.list_reminders({}) == "No open reminders."


def test_add_reminder_requires_text(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    assert reminders_module.add_reminder({"text": "  "}).startswith("error:")


def test_search_notes_finds_matching_lines(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_NOTES_DIR", str(tmp_path))
    (tmp_path / "work.md").write_text("Standup is at 9:30am.\nUnrelated line.\n")

    result = notes_module.search_notes({"query": "standup"})
    assert "work.md:1" in result
    assert "9:30am" in result


def test_search_notes_reports_no_matches(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_NOTES_DIR", str(tmp_path))
    (tmp_path / "work.md").write_text("nothing relevant here\n")

    result = notes_module.search_notes({"query": "standup"})
    assert "No matches" in result


def test_search_notes_requires_query(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_NOTES_DIR", str(tmp_path))
    assert notes_module.search_notes({"query": ""}).startswith("error:")
