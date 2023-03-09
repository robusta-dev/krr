from __future__ import annotations

import itertools
from typing import Any

import pydantic as pd

from robusta_krr.core.abstract.formatters import BaseFormatter
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.core.models.allocations import ResourceAllocations, ResourceType


class ResourceScan(pd.BaseModel):
    object: K8sObjectData
    recommended: ResourceAllocations


class Result(pd.BaseModel):
    scans: list[ResourceScan]
    score: float = 0.0

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.score = self.__calculate_score()

    def format(self, formatter: type[BaseFormatter] | str, **kwargs: Any) -> Any:
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
    def __percentage_difference(current: float | str | None, recommended: float | str | None) -> float:
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

        return max(0, round(100 - total_diff / len(self.scans) / len(ResourceType) / 50, 2))  # 50 is just a constant
