"""Built-in heartbeat checks.

Each check is a small function `(params: dict) -> CheckResult | None`.
Returning `None` — "nothing worth surfacing" — is the expected outcome
most of the time; that's what "quiet by default" means in practice. Add
a new capability by writing one function here, adding it to `CHECKS`,
then turning it on in `config.yaml` — nothing else needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..tools.notes import search_notes
from ..tools.reminders import load_reminders


@dataclass
class CheckResult:
    level: str  # "log" | "interrupt" | "critical"
    text: str


def notes_watch(params: dict) -> CheckResult | None:
    """Surface an interruption if a configured phrase shows up in notes.

    This is the check meant for exercising the heartbeat end to end: add
    a line containing `params["query"]` to a note and the next due tick
    should surface it.
    """
    query = (params.get("query") or "").strip()
    if not query:
        return None
    result = search_notes({"query": query})
    if result.startswith("No matches") or result.startswith("error:"):
        return None
    return CheckResult(level="interrupt", text=f"Found {query!r} in your notes:\n{result}")


def open_reminders_digest(params: dict) -> CheckResult | None:
    """A quiet, log-only digest of open reminders.

    Produces nothing when there's nothing open, so it stays out of the
    way — it only ever shows up in the calm log, never as an
    interruption, per AGENT.md's "most checks produce nothing" rule.
    """
    open_reminders = [r for r in load_reminders() if not r.get("done")]
    if not open_reminders:
        return None
    lines = "\n".join(f"- {r['text']}" for r in open_reminders)
    return CheckResult(level="log", text=f"{len(open_reminders)} open reminder(s):\n{lines}")


CHECKS = {
    "notes_watch": notes_watch,
    "open_reminders_digest": open_reminders_digest,
}
