"""Planner for task and motion decisions."""

from typing import Any, Dict

from robot_assistant.config.defaults import RuntimeConfig


class Planner:
    """Produces plans based on goals, constraints, and current context."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config

    def build_plan(self, intents: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Return a placeholder plan object."""
        return {"intents": intents, "state": state}
