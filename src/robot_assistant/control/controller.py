"""Controller that maps plans to actuator commands."""

from typing import Any, Dict

from robot_assistant.config.defaults import RuntimeConfig
from robot_assistant.hardware.interfaces import HardwareSuite


class Controller:
    """Closed-loop controller placeholder."""

    def __init__(self, hardware: HardwareSuite, config: RuntimeConfig) -> None:
        self.hardware = hardware
        self.config = config

    def execute(self, plan: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Translate a plan into actuator commands."""
        return {"plan": plan, "state": state}
