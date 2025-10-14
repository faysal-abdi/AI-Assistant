"""Abstract interfaces for hardware components."""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class SensorPacket:
    """Structured sensor sample."""

    data: Dict[str, Any]


class HardwareSuite:
    """Aggregate hardware interface managing sensors and actuators."""

    def read_sensors(self) -> SensorPacket:
        """Collect a snapshot from all sensors."""
        return SensorPacket(data={})

    def apply_commands(self, commands: Dict[str, Any]) -> None:
        """Send command setpoints to actuators."""

    def shutdown(self) -> None:
        """Release hardware resources."""
