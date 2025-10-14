"""Telemetry helpers for latency measurement."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Dict, Iterable, List


@dataclass
class StageMeasurement:
    """Individual timing measurement for a named stage."""

    stage: str
    duration_ms: float


class LatencyProbe:
    """Collects stage-level latency metrics for diagnostic usage."""

    def __init__(self) -> None:
        self._measurements: List[StageMeasurement] = []

    @contextmanager
    def track(self, stage: str) -> Iterable[None]:
        """Context manager that records elapsed time for a block."""
        start = perf_counter()
        try:
            yield
        finally:
            duration_ms = (perf_counter() - start) * 1000.0
            self._measurements.append(StageMeasurement(stage=stage, duration_ms=duration_ms))

    def flush(self) -> List[StageMeasurement]:
        """Return and clear collected measurements."""
        measurements = list(self._measurements)
        self._measurements.clear()
        return measurements

    def summary(self) -> Dict[str, float]:
        """Aggregate measurements by stage (average duration)."""
        aggregates: Dict[str, List[float]] = {}
        for item in self._measurements:
            aggregates.setdefault(item.stage, []).append(item.duration_ms)
        return {
            stage: sum(values) / len(values)
            for stage, values in aggregates.items()
        }
