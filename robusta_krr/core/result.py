import pydantic as pd
import enum

from robusta_krr.core.formatters import BaseFormatter, get_formatter, FormatType


class ResourceRecommendation(pd.BaseModel):
    current: float
    recommended: float


class ResourceType(str, enum.Enum):
    cpu = "cpu"
    memory = "memory"


class ObjectData(pd.BaseModel):
    name: str
    kind: str
    namespace: str


class ResourceScan(pd.BaseModel):
    object: ObjectData
    requests: dict[ResourceType, ResourceRecommendation]
    limits: dict[ResourceType, ResourceRecommendation]


class Result(pd.BaseModel):
    scans: list[ResourceScan]

    def format(self, formatter: BaseFormatter | FormatType) -> str:
        """Format the result.

        Args:
            formatter: The formatter to use.

        Returns:
            The formatted result.
        """

        if isinstance(formatter, str):
            formatter = get_formatter(formatter)

        return formatter.format(self)
