"""Perception pipeline ingesting sensor data and producing state estimates."""

from typing import Any, Dict

from robot_assistant.hardware.interfaces import HardwareSuite, SensorPacket


class PerceptionPipeline:
    """Transforms raw sensor packets into a shared state representation."""

    def __init__(self, hardware: HardwareSuite) -> None:
        self.hardware = hardware

    def process(self, packet: SensorPacket) -> Dict[str, Any]:
        """Convert sensor data into state features."""
        return {"raw": packet.data}
