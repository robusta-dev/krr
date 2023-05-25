from __future__ import annotations

import abc
from typing import Callable, Optional, TypeVar

from robusta_krr.core.models.allocations import ResourceType
from robusta_krr.core.models.severity import Severity


class BaseSeverityCalculator(abc.ABC):
    # Is here as we are creating this object in get_by_resource method, so it can not have any arguments
    def __init__(self) -> None:
        ...

    @abc.abstractmethod
    def calculate(self, current: Optional[float], recommended: Optional[float]) -> Severity:
        ...

    @staticmethod
    def get_by_resource(resource: ResourceType) -> BaseSeverityCalculator:
        from robusta_krr.core.models.severity_calculator.default_calculator import DefaultSeverityCalculator

        return SEVERITY_CALCULATORS_MAP.get(resource, DefaultSeverityCalculator)()


Self = TypeVar("Self", bound=BaseSeverityCalculator)
SEVERITY_CALCULATORS_MAP: dict[ResourceType, type[BaseSeverityCalculator]] = {}


def bind_calculator(resource_type: ResourceType) -> Callable[[type[Self]], type[Self]]:
    def decorator(cls: type[Self]) -> type[Self]:
        SEVERITY_CALCULATORS_MAP[resource_type] = cls
        return cls

    return decorator
