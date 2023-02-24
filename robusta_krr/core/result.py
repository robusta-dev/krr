import enum
from typing import Any

import pydantic as pd

from robusta_krr.core.formatters import BaseFormatter
from robusta_krr.core.objects import K8sObjectData


class ResourceType(str, enum.Enum):
    cpu = "cpu"
    memory = "memory"


class ResourceAllocations(pd.BaseModel):
    requests: dict[ResourceType, float]
    limits: dict[ResourceType, float]


class ResourceScan(pd.BaseModel):
    object: K8sObjectData
    current: ResourceAllocations
    recommended: ResourceAllocations


class Result(pd.BaseModel):
    scans: list[ResourceScan]

    def format(self, formatter: type[BaseFormatter] | str, **kwargs: Any) -> str:
        """Format the result.

        Args:
            formatter: The formatter to use.

        Returns:
            The formatted result.
        """

        FormatterType = BaseFormatter.find(formatter) if isinstance(formatter, str) else formatter
        _formatter = FormatterType(**kwargs)
        return _formatter.format(self)
