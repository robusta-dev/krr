from __future__ import annotations

import enum
import itertools
from typing import Any, Union

import pydantic as pd

from robusta_krr.core.abstract.formatters import BaseFormatter
from robusta_krr.core.models.allocations import RecommendationValue, ResourceAllocations, ResourceType
from robusta_krr.core.models.objects import K8sObjectData


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
    def calculate(cls, current: RecommendationValue, recommended: RecommendationValue) -> Severity:
        if isinstance(recommended, str) or isinstance(current, str):
            return cls.UNKNOWN

        if current is None and recommended is None:
            return cls.OK
        if current is None or recommended is None:
            return cls.WARNING

        diff = (current - recommended) / recommended

        if diff > 1.0 or diff < -0.5:
            return cls.CRITICAL
        elif diff > 0.5 or diff < -0.25:
            return cls.WARNING
        else:
            return cls.GOOD


class ResourceScan(pd.BaseModel):
    object: K8sObjectData
    recommended: ResourceAllocations
    severity: Severity = None  # type: ignore

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        severities = [Severity.UNKNOWN]

        for resource_type in ResourceType:
            for selector in ["requests", "limits"]:
                current = getattr(self.object.allocations, selector).get(resource_type)
                recommended = getattr(self.recommended, selector).get(resource_type)

                severities.append(Severity.calculate(current, recommended))

        for severity in [Severity.CRITICAL, Severity.WARNING, Severity.OK, Severity.GOOD, Severity.UNKNOWN]:
            if severity in severities:
                self.severity = severity
                break


class Result(pd.BaseModel):
    scans: list[ResourceScan]
    score: float = 0.0

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.score = self.__calculate_score()

    def format(self, formatter: Union[type[BaseFormatter], str], **kwargs: Any) -> Any:
        """Format the result.

        Args:
            formatter: The formatter to use.

        Returns:
            The formatted result.
        """

        FormatterType = BaseFormatter.find(formatter) if isinstance(formatter, str) else formatter
        _formatter = FormatterType(**kwargs)
        return _formatter.format(self)

    @staticmethod
    def __percentage_difference(current: RecommendationValue, recommended: RecommendationValue) -> float:
        """Get the percentage difference between two numbers.

        Args:
            current: The current value.
            recommended: The recommended value.

        Returns:
            The percentage difference.
        """

        return 1

    def __calculate_score(self) -> float:
        """Get the score of the result.

        Returns:
            The score of the result.
        """

        total_diff = 0.0
        for scan, resource_type in itertools.product(self.scans, ResourceType):
            total_diff += self.__percentage_difference(
                scan.object.allocations.requests[resource_type], scan.recommended.requests[resource_type]
            )
            total_diff += self.__percentage_difference(
                scan.object.allocations.limits[resource_type], scan.recommended.limits[resource_type]
            )

        if len(self.scans) == 0:
            return 0.0

        return max(0, round(100 - total_diff / len(self.scans) / len(ResourceType) / 50, 2))  # 50 is just a constant
