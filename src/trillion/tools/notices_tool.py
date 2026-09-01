"""Exposes the heartbeat's notice inbox as tools.

Surfacing and dismissing proactive notices happens through the same
conversation as everything else — per AGENT.md's "one shared agent core"
rule, the heartbeat doesn't get its own separate UI.
"""

from __future__ import annotations

from ..heartbeat.notices import dismiss_notice, list_notices
from .registry import Tool


def list_notices_tool(tool_input: dict) -> str:
    notices = list_notices(include_dismissed=False)
    if not notices:
        return "No pending notices."
    return "\n".join(
        f"[{n.id}] ({n.level}, from {n.check_name}) {n.text}" for n in notices
    )


def dismiss_notice_tool(tool_input: dict) -> str:
    notice_id = (tool_input.get("id") or "").strip()
    if not notice_id:
        return "error: 'id' is required"
    if dismiss_notice(notice_id):
        return f"Dismissed [{notice_id}]"
    return f"error: no notice with id {notice_id!r}"


LIST_NOTICES = Tool(
    name="list_notices",
    description=(
        "List proactive notices the heartbeat has surfaced (from "
        "background checks) that the user hasn't dismissed yet."
    ),
    input_schema={"type": "object", "properties": {}},
    handler=list_notices_tool,
)

DISMISS_NOTICE = Tool(
    name="dismiss_notice",
    description=(
        "Dismiss a proactive notice once it's been seen or handled, "
        "given its id (shown by list_notices)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "The id of the notice to dismiss."},
        },
        "required": ["id"],
    },
    handler=dismiss_notice_tool,
)
