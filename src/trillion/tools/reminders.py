"""Reminders & tasks — the first capability, per AGENT.md.

Reminders are stored as a small JSON file so they survive a restart even
though full durable memory (facts about the user, editable by hand)
doesn't land until Tier 4. This store is just for reminders, kept as
plain, inspectable JSON on purpose.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .registry import Tool


def _data_dir() -> Path:
    path = Path(os.environ.get("TRILLION_DATA_DIR", "./data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _store_path() -> Path:
    return _data_dir() / "reminders.json"


def _load() -> list[dict]:
    path = _store_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return []


def _save(reminders: list[dict]) -> None:
    _store_path().write_text(json.dumps(reminders, indent=2))


def add_reminder(tool_input: dict) -> str:
    text = (tool_input.get("text") or "").strip()
    if not text:
        return "error: 'text' is required and can't be empty"
    due = (tool_input.get("due") or "").strip() or None

    reminder = {
        "id": uuid.uuid4().hex[:8],
        "text": text,
        "due": due,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "done": False,
    }
    reminders = _load()
    reminders.append(reminder)
    _save(reminders)

    due_note = f" (due {due})" if due else ""
    return f"Reminder added [{reminder['id']}]: {text}{due_note}"


def list_reminders(tool_input: dict) -> str:
    open_reminders = [r for r in _load() if not r.get("done")]
    if not open_reminders:
        return "No open reminders."
    lines = []
    for r in open_reminders:
        due_note = f" (due {r['due']})" if r.get("due") else ""
        lines.append(f"[{r['id']}] {r['text']}{due_note}")
    return "\n".join(lines)


def complete_reminder(tool_input: dict) -> str:
    reminder_id = (tool_input.get("id") or "").strip()
    if not reminder_id:
        return "error: 'id' is required"
    reminders = _load()
    for r in reminders:
        if r["id"] == reminder_id:
            r["done"] = True
            _save(reminders)
            return f"Marked [{reminder_id}] done: {r['text']}"
    return f"error: no reminder with id {reminder_id!r}"


ADD_REMINDER = Tool(
    name="add_reminder",
    description=(
        "Add a new reminder/task for the user to be tracked. Use this "
        "whenever the user asks to be reminded of something or wants to "
        "add something to their to-do list."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "What to remind the user about."},
            "due": {
                "type": "string",
                "description": (
                    "Optional plain-language due date/time, e.g. "
                    "'tomorrow at 9am'. Omit if the user didn't give one."
                ),
            },
        },
        "required": ["text"],
    },
    handler=add_reminder,
)

LIST_REMINDERS = Tool(
    name="list_reminders",
    description="List the user's current open (not-yet-completed) reminders/tasks.",
    input_schema={"type": "object", "properties": {}},
    handler=list_reminders,
)

COMPLETE_REMINDER = Tool(
    name="complete_reminder",
    description=(
        "Mark a reminder/task as done, given its short id (shown in "
        "brackets by list_reminders)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "The short id of the reminder to complete."},
        },
        "required": ["id"],
    },
    handler=complete_reminder,
)
