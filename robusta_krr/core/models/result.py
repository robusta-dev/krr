from __future__ import annotations

from typing import Any, Optional, Union

import pydantic as pd

from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.allocations import RecommendationValue, ResourceAllocations, ResourceType
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.core.models.severity import Severity
from robusta_krr.core.models.config import Config


class Recommendation(pd.BaseModel):
    value: RecommendationValue
    severity: Severity


class ResourceRecommendation(pd.BaseModel):
    requests: dict[ResourceType, Union[RecommendationValue, Recommendation]]
    limits: dict[ResourceType, Union[RecommendationValue, Recommendation]]
    info: dict[ResourceType, Optional[str]]


class ResourceScan(pd.BaseModel):
    object: K8sObjectData
    recommended: ResourceRecommendation
    severity: Severity

    @classmethod
    def calculate(cls, object: K8sObjectData, recommendation: ResourceAllocations) -> ResourceScan:
        recommendation_processed = ResourceRecommendation(requests={}, limits={}, info={})

        for resource_type in ResourceType:
            recommendation_processed.info[resource_type] = recommendation.info.get(resource_type)

            for selector in ["requests", "limits"]:
                current = getattr(object.allocations, selector).get(resource_type)
                recommended = getattr(recommendation, selector).get(resource_type)

                current_severity = Severity.calculate(current, recommended, resource_type)

                #TODO: consider... changing field after model created doesn't validate it.
                getattr(recommendation_processed, selector)[resource_type] = Recommendation(
                    value=recommended, severity=current_severity
                )

        for severity in [Severity.CRITICAL, Severity.WARNING, Severity.OK, Severity.GOOD, Severity.UNKNOWN]:
            for selector in ["requests", "limits"]:
                for recommendation_request in getattr(recommendation_processed, selector).values():
                    if recommendation_request.severity == severity:
                        return cls(object=object, recommended=recommendation_processed, severity=severity)

        return cls(object=object, recommended=recommendation_processed, severity=Severity.UNKNOWN)


class StrategyData(pd.BaseModel):
    name: str
    settings: dict[str, Any]


class Result(pd.BaseModel):
    scans: list[ResourceScan]
    score: int = 0
    resources: list[str] = ["cpu", "memory"]
    description: Optional[str] = None
    strategy: StrategyData
    errors: list[dict[str, Any]] = pd.Field(default_factory=list)
    clusterSummary: dict[str, Any] = {}
    config: Optional[Config] = pd.Field(default_factory=Config.get_config)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.score = self.__calculate_score()

    def format(self, formatter: Union[formatters.FormatterFunc, str]) -> Any:
        """Format the result.

        Args:
            formatter: The formatter to use.

        Returns:
            The formatted result.
        """

        formatter = formatters.find(formatter) if isinstance(formatter, str) else formatter
        return formatter(self)

    @staticmethod
    def __scan_cost(scan: ResourceScan) -> float:
        return 0.7 if scan.severity == Severity.WARNING else 1 if scan.severity == Severity.CRITICAL else 0

    def __calculate_score(self) -> int:
        """Get the score of the result.

        Returns:
            The score of the result.
        """

        score = sum(self.__scan_cost(scan) for scan in self.scans)
        return int((len(self.scans) - score) / len(self.scans) * 100) if self.scans else 0

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
