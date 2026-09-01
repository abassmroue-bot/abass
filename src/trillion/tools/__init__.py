"""The tool registry and the built-in tools Trillion ships with.

Adding a new capability should mean writing one self-contained tool
module and registering it in `build_registry()` below — never editing the
conversation loop in `trillion.brain`.
"""

from .notes import SEARCH_NOTES
from .registry import Tool, ToolRegistry
from .reminders import ADD_REMINDER, COMPLETE_REMINDER, LIST_REMINDERS


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in (ADD_REMINDER, LIST_REMINDERS, COMPLETE_REMINDER, SEARCH_NOTES):
        registry.register(tool)
    return registry


__all__ = ["Tool", "ToolRegistry", "build_registry"]
