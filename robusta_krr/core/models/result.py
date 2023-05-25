from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional, Union

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
    def calculate(
        cls, current: RecommendationValue, recommended: RecommendationValue, resource_type: ResourceType
    ) -> Severity:
        if isinstance(recommended, str) or isinstance(current, str):
            return cls.UNKNOWN

        if current is None and recommended is None:
            return cls.GOOD
        if current is None or recommended is None:
            return cls.WARNING

        diff = abs(current - recommended)

        if resource_type == ResourceType.CPU:
            if diff >= 0.5:
                return cls.CRITICAL
            elif diff >= 0.25:
                return cls.WARNING
            elif diff >= 0.1:
                return cls.OK
            else:
                return cls.GOOD
        else:
            diff_megabytes = diff / 1024 / 1024
            if diff_megabytes >= 500:
                return cls.CRITICAL
            elif diff_megabytes >= 250:
                return cls.WARNING
            elif diff_megabytes >= 100:
                return cls.OK
            else:
                return cls.GOOD


class Recommendation(pd.BaseModel):
    value: RecommendationValue
    severity: Severity


class ResourceRecommendation(pd.BaseModel):
    requests: dict[ResourceType, RecommendationValue]
    limits: dict[ResourceType, RecommendationValue]


class Metric(pd.BaseModel):
    query: str
    start_time: datetime
    end_time: datetime
    step: str


MetricsData = dict[ResourceType, Metric]


class ResourceScan(pd.BaseModel):
    object: K8sObjectData
    recommended: ResourceRecommendation
    severity: Severity
    metrics: MetricsData

    @classmethod
    def calculate(
        cls, object: K8sObjectData, recommendation: ResourceAllocations, metrics: MetricsData
    ) -> ResourceScan:
        recommendation_processed = ResourceRecommendation(requests={}, limits={})

        for resource_type in ResourceType:
            for selector in ["requests", "limits"]:
                current = getattr(object.allocations, selector).get(resource_type)
                recommended = getattr(recommendation, selector).get(resource_type)

                current_severity = Severity.calculate(current, recommended, resource_type)

                getattr(recommendation_processed, selector)[resource_type] = Recommendation(
                    value=recommended, severity=current_severity
                )

        for severity in [Severity.CRITICAL, Severity.WARNING, Severity.OK, Severity.GOOD, Severity.UNKNOWN]:
            for selector in ["requests", "limits"]:
                for recommendation_request in getattr(recommendation_processed, selector).values():
                    if recommendation_request.severity == severity:
                        return cls(
                            object=object, recommended=recommendation_processed, severity=severity, metrics=metrics
                        )

        return cls(object=object, recommended=recommendation_processed, severity=Severity.UNKNOWN, metrics=metrics)


class Result(pd.BaseModel):
    scans: list[ResourceScan]
    score: int = 0
    resources: list[str] = ["cpu", "memory"]
    description: Optional[str] = None

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
    def __scan_cost(scan: ResourceScan) -> float:
        return 0.7 if scan.severity == Severity.WARNING else 1 if scan.severity == Severity.CRITICAL else 0

    def __calculate_score(self) -> int:
        """Get the score of the result.

        Returns:
            The score of the result.
        """

        score = sum(self.__scan_cost(scan) for scan in self.scans)
        return int((len(self.scans) - score) / len(self.scans) * 100)

    @property
    def score_letter(self) -> str:
        return (
            "F"
            if self.score < 30
            else "D"
            if self.score < 55
            else "C"
            if self.score < 70
            else "B"
            if self.score < 90
            else "A"
        )
