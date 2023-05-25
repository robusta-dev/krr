from __future__ import annotations

import enum

from robusta_krr.core.models.allocations import RecommendationValue, ResourceType


class Severity(str, enum.Enum):
    """The severity of the scan."""

    UNKNOWN = "UNKNOWN"
    GOOD = "GOOD"
    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

    @property
    def color(self) -> str:
        return {
            self.UNKNOWN: "dim",
            self.GOOD: "green",
            self.OK: "gray",
            self.WARNING: "yellow",
            self.CRITICAL: "red",
        }[self]

    @classmethod
    def calculate(
        cls, current: RecommendationValue, recommended: RecommendationValue, resource_type: ResourceType
    ) -> Severity:
        from robusta_krr.core.models.severity_calculator import BaseSeverityCalculator

        if isinstance(recommended, str) or isinstance(current, str):
            return cls.UNKNOWN

        return BaseSeverityCalculator.get_by_resource(resource_type).calculate(current, recommended)
