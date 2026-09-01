"""Durable memory — facts about the user that survive a restart.

This is long-term memory (Tier 4), separate from the in-session
conversation history in `Brain.history`. Stored as a small, plain,
human-editable file: one fact per line, so it can be opened, corrected,
or deleted with any text editor, never a special tool.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from .registry import Tool

_LINE_PATTERN = re.compile(r"^-\s*\[(?P<id>[0-9a-f]{8})\]\s*(?P<text>.+)$")
_HEADER = "# Trillion's memory — one fact per line. Edit or delete freely; it's read fresh every turn.\n"


def _data_dir() -> Path:
    path = Path(os.environ.get("TRILLION_DATA_DIR", "./data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _store_path() -> Path:
    return _data_dir() / "memory.md"


def load_facts() -> list[dict]:
    """Load the current facts, oldest first.

    Cheap enough to call on every turn — which is exactly what makes a
    fact edited by hand, or remembered mid-conversation, take effect
    immediately rather than only after a restart.
    """
    path = _store_path()
    if not path.exists():
        return []
    facts = []
    for line in path.read_text().splitlines():
        match = _LINE_PATTERN.match(line.strip())
        if match:
            facts.append({"id": match.group("id"), "text": match.group("text")})
    return facts


def _save(facts: list[dict]) -> None:
    lines = [_HEADER.rstrip("\n"), ""]
    lines += [f"- [{f['id']}] {f['text']}" for f in facts]
    _store_path().write_text("\n".join(lines) + "\n")


def remember_fact(tool_input: dict) -> str:
    text = (tool_input.get("text") or "").strip()
    if not text:
        return "error: 'text' is required and can't be empty"
    facts = load_facts()
    fact = {"id": uuid.uuid4().hex[:8], "text": text}
    facts.append(fact)
    _save(facts)
    return f"Remembered [{fact['id']}]: {text}"


def list_facts_tool(tool_input: dict) -> str:
    facts = load_facts()
    if not facts:
        return "No facts remembered yet."
    return "\n".join(f"[{f['id']}] {f['text']}" for f in facts)


def update_fact(tool_input: dict) -> str:
    fact_id = (tool_input.get("id") or "").strip()
    text = (tool_input.get("text") or "").strip()
    if not fact_id or not text:
        return "error: both 'id' and 'text' are required"
    facts = load_facts()
    for fact in facts:
        if fact["id"] == fact_id:
            fact["text"] = text
            _save(facts)
            return f"Updated [{fact_id}]: {text}"
    return f"error: no remembered fact with id {fact_id!r}"


def forget_fact(tool_input: dict) -> str:
    fact_id = (tool_input.get("id") or "").strip()
    if not fact_id:
        return "error: 'id' is required"
    facts = load_facts()
    remaining = [fact for fact in facts if fact["id"] != fact_id]
    if len(remaining) == len(facts):
        return f"error: no remembered fact with id {fact_id!r}"
    _save(remaining)
    return f"Forgot [{fact_id}]"


REMEMBER_FACT = Tool(
    name="remember_fact",
    description=(
        "Save a durable fact about the user for future conversations — "
        "an identity detail, a preference, or a decision worth "
        "remembering long-term. One clear statement per fact. Don't use "
        "this for passing chatter that only matters in this conversation."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The fact to remember, written as one plain statement.",
            },
        },
        "required": ["text"],
    },
    handler=remember_fact,
)

LIST_FACTS = Tool(
    name="list_facts",
    description="List everything currently remembered about the user long-term.",
    input_schema={"type": "object", "properties": {}},
    handler=list_facts_tool,
)

UPDATE_FACT = Tool(
    name="update_fact",
    description="Correct a previously remembered fact, given its id (shown by list_facts).",
    input_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "The short id of the fact to update."},
            "text": {"type": "string", "description": "The corrected fact."},
        },
        "required": ["id", "text"],
    },
    handler=update_fact,
)

FORGET_FACT = Tool(
    name="forget_fact",
    description=(
        "Remove a previously remembered fact that's no longer true or "
        "relevant, given its id (shown by list_facts)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "The short id of the fact to forget."},
        },
        "required": ["id"],
    },
    handler=forget_fact,
)
