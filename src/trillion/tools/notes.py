"""Answering questions about the user's notes — the second capability,
per AGENT.md.

Tier 2 keeps this deliberately simple: a plain-text search over a notes
directory. It's a real, useful tool today and an obvious seam to upgrade
later (e.g. to embeddings-based retrieval) without touching the registry
or the conversation loop.
"""

from __future__ import annotations

import os
from pathlib import Path

from .registry import Tool


def _notes_dir() -> Path:
    return Path(os.environ.get("TRILLION_NOTES_DIR", "./notes"))


def search_notes(tool_input: dict) -> str:
    query = (tool_input.get("query") or "").strip()
    if not query:
        return "error: 'query' is required and can't be empty"

    notes_dir = _notes_dir()
    if not notes_dir.is_dir():
        return f"error: notes directory {notes_dir} doesn't exist"

    needle = query.lower()
    matches: list[str] = []
    for path in sorted(notes_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if needle in line.lower():
                matches.append(f"{path.relative_to(notes_dir)}:{line_no}: {line.strip()}")

    if not matches:
        return f"No matches for {query!r} in {notes_dir}."
    return "\n".join(matches[:20])


SEARCH_NOTES = Tool(
    name="search_notes",
    description=(
        "Search the user's local notes for lines matching a query. Use "
        "this to answer questions about what's in the user's notes/files "
        "before saying you don't know or don't have access."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A word or phrase to search for in the notes.",
            },
        },
        "required": ["query"],
    },
    handler=search_notes,
)
