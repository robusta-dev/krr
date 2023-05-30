from __future__ import annotations

import enum
from typing import Callable, Optional

from robusta_krr.core.models.allocations import RecommendationValue, ResourceType


class Severity(str, enum.Enum):
    """
    The severity of the scan.

    The severity is calculated based on the difference between the current value and the recommended value.
    You can override the severity calculation function by using the `bind_calculator` decorator from the same module.
    """

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
        if isinstance(recommended, str) or isinstance(current, str):
            return cls.UNKNOWN

        return calculate_severity(current, recommended, resource_type)


def register_severity_calculator(resource_type: ResourceType) -> Callable[[SeverityCalculator], SeverityCalculator]:
    """
    Bind a severity calculator function to a resource type.
    Use this decorator to bind a severity calculator function to a resource type.

    Example:
    >>> @bind_severity_calculator(ResourceType.CPU)
    >>> def cpu_severity_calculator(current: Optional[float], recommended: Optional[float], resource_type: ResourceType) -> Severity:
    >>>     if current is None and recommended is None:
    >>>         return Severity.GOOD
    >>>     if current is None or recommended is None:
    >>>         return Severity.WARNING
    >>>
    >>>     return Severity.CRITICAL if abs(current - recommended) >= 0.5 else Severity.GOOD
    """

    def decorator(func: SeverityCalculator) -> SeverityCalculator:
        SEVERITY_CALCULATORS_REGISTRY[resource_type] = func
        return func

    return decorator


SeverityCalculator = Callable[[Optional[float], Optional[float], ResourceType], Severity]
SEVERITY_CALCULATORS_REGISTRY: dict[ResourceType, SeverityCalculator] = {}


def calculate_severity(current: Optional[float], recommended: Optional[float], resource_type: ResourceType) -> Severity:
    """
    Calculate the severity of the scan based on the current value and the recommended value.

    This function will use the severity calculator function that is bound to the resource type.
    If there is no calculator function bound to the resource type, it will use the default severity calculator function.
    """

    return SEVERITY_CALCULATORS_REGISTRY.get(resource_type, default_severity_calculator)(
        current, recommended, resource_type
    )


def default_severity_calculator(
    current: Optional[float], recommended: Optional[float], resource_type: ResourceType
) -> Severity:
    return Severity.UNKNOWN


@register_severity_calculator(ResourceType.CPU)
def cpu_severity_calculator(
    current: Optional[float], recommended: Optional[float], resource_type: ResourceType
) -> Severity:
    if current is None and recommended is None:
        return Severity.GOOD
    if current is None or recommended is None:
        return Severity.WARNING

    diff = abs(current - recommended)

    if diff >= 0.5:
        return Severity.CRITICAL
    elif diff >= 0.25:
        return Severity.WARNING
    elif diff >= 0.1:
        return Severity.OK
    else:
        return Severity.GOOD


@register_severity_calculator(ResourceType.Memory)
def memory_severity_calculator(
    current: Optional[float], recommended: Optional[float], resource_type: ResourceType
) -> Severity:
    if current is None and recommended is None:
        return Severity.GOOD
    if current is None or recommended is None:
        return Severity.WARNING

    diff = abs(current - recommended) / 1024 / 1024

    if diff >= 500:
        return Severity.CRITICAL
    elif diff >= 250:
        return Severity.WARNING
    elif diff >= 100:
        return Severity.OK
    else:
        return Severity.GOOD
