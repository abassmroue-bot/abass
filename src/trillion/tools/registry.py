"""A registry of tools the model can choose to call.

Each tool is registered once with a name, a clear description of *when*
to use it (the model picks tools by reading these, not by reading code),
and a JSON schema for its inputs. The registry is the seam that lets the
assistant grow capabilities without the conversation loop ever changing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..config import get_confirmation_required_tools


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], str]
    # Tier 6 will enforce this: any tool that sends, spends, deletes, or
    # changes a setting must be registered with requires_confirmation=True
    # and must not run until the user has explicitly said yes.
    requires_confirmation: bool = False

    def spec(self) -> dict:
        """The shape the model provider expects to see."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self) -> list[dict]:
        return [tool.spec() for tool in self._tools.values()]

    def requires_confirmation(self, name: str) -> bool:
        """Whether `name` must go through the confirmation gate before it
        runs — true if the tool itself says so, or if config.yaml's
        `tools.require_confirmation` list names it. Config can only widen
        this, never narrow it below what the tool's own code declares."""
        tool = self.get(name)
        if tool is None:
            return False
        return tool.requires_confirmation or name in get_confirmation_required_tools()

    def run(self, name: str, tool_input: dict) -> str:
        """Run a tool by name and return a plain-text result for the model.

        Never raises: a bad input, a missing file, or a bug in the tool
        itself comes back as a readable error string so the model can
        react to it (explain the problem, try something else, ask me)
        instead of the whole conversation crashing.
        """
        tool = self.get(name)
        if tool is None:
            return f"error: no such tool {name!r}"
        try:
            return tool.handler(tool_input)
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
            return f"error: {tool.name} failed: {exc}"
