"""Manage privilege tiers, pauses, and audit logging for tool execution."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from robot_assistant.config.defaults import SafetyConfig


_COMMAND_CATEGORIES = {"control", "system", "home_automation"}


@dataclass
class SafetyStatus:
    """Result of privilege enforcement."""

    allowed: bool
    reason: str = ""


class SafetyManager:
    """Centralizes privilege state, pause control, and audit logging."""

    def __init__(self, config: SafetyConfig) -> None:
        self.config = config
        self.privilege_level = config.default_privilege
        self.paused = config.pause_on_start
        self.log_path = Path(config.audit_log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def set_privilege(self, level: str) -> None:
        """Update the privilege level."""
        normalized = level.lower()
        if normalized not in ("informational", "command"):
            raise ValueError("Unsupported privilege level")
        self.privilege_level = normalized
        self._log_event(
            event="privilege_change",
            detail={"level": self.privilege_level},
        )

    def pause(self) -> None:
        """Pause privileged actions."""
        self.paused = True
        self._log_event(event="paused", detail={})

    def resume(self) -> None:
        """Resume privileged actions."""
        self.paused = False
        self._log_event(event="resumed", detail={})

    def is_allowed(self, tool_category: str) -> SafetyStatus:
        """Check whether a tool category is allowed under current settings."""
        if self.paused:
            return SafetyStatus(False, "safety_paused")
        if self.privilege_level == "informational" and tool_category in _COMMAND_CATEGORIES:
            return SafetyStatus(False, "insufficient_privilege")
        return SafetyStatus(True, "")

    def log_tool(self, name: str, category: str, outcome: str, metadata: Dict[str, str]) -> None:
        """Append a tool execution event to the audit log."""
        detail = {"tool": name, "category": category, "outcome": outcome, **metadata}
        self._log_event(event="tool", detail=detail)

    def _log_event(self, event: str, detail: Dict[str, str]) -> None:
        payload = {
            "ts": time.time(),
            "event": event,
            "detail": detail,
            "privilege": self.privilege_level,
            "paused": self.paused,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
