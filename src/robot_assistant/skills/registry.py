"""Skill registry managing task-oriented behaviors."""

from typing import Any, Dict, Callable

from robot_assistant.planning.planner import Planner
from robot_assistant.control.controller import Controller


SkillHandler = Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


class SkillRegistry:
    """Registers and dispatches skills based on incoming intents."""

    def __init__(self, planner: Planner, controller: Controller) -> None:
        self.planner = planner
        self.controller = controller
        self._skills: Dict[str, SkillHandler] = {"default": self._default_skill}

    def register(self, name: str, handler: SkillHandler) -> None:
        """Add a new skill handler."""
        self._skills[name] = handler

    def dispatch(self, intents: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Select an appropriate skill to handle intents."""
        skill_name = intents.get("skill", "default")
        handler = self._skills.get(skill_name, self._default_skill)
        return handler(intents, state)

    def _default_skill(self, intents: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback behavior when no specialized skill matches."""
        plan = self.planner.build_plan(intents, state)
        return plan
