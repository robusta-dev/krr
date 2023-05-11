from __future__ import annotations

import enum
import math
from typing import Literal, TypeVar, Union

import pydantic as pd
from kubernetes.client.models import V1Container

from robusta_krr.utils import resource_units


class ResourceType(str, enum.Enum):
    """The type of resource.

    Just add new types here and they will be automatically supported.
    """

    CPU = "cpu"
    Memory = "memory"


RecommendationValue = Union[float, Literal["?"], None]
RecommendationValueRaw = Union[float, str, None]

Self = TypeVar("Self", bound="ResourceAllocations")


class ResourceAllocations(pd.BaseModel):
    requests: dict[ResourceType, RecommendationValue]
    limits: dict[ResourceType, RecommendationValue]

    @staticmethod
    def __parse_resource_value(value: RecommendationValueRaw) -> RecommendationValue:
        if value is None:
            return None

        if isinstance(value, str):
            return float(resource_units.parse(value))

        if math.isnan(value):
            return "?"

        return float(value)

    @pd.validator("requests", "limits", pre=True)
    def validate_requests(
        cls, value: dict[ResourceType, RecommendationValueRaw]
    ) -> dict[ResourceType, RecommendationValue]:
        return {
            resource_type: cls.__parse_resource_value(resource_value) for resource_type, resource_value in value.items()
        }

    @classmethod
    def from_container(cls: type[Self], container: V1Container) -> Self:
        """Get the resource allocations from a Kubernetes container.

        Args:
            container: The Kubernetes container.

        Returns:
            The resource allocations.
        """

        return cls(
            requests={
                ResourceType.CPU: container.resources.requests.get("cpu")
                if container.resources and container.resources.requests
                else None,
                ResourceType.Memory: container.resources.requests.get("memory")
                if container.resources and container.resources.requests
                else None,
            },
            limits={
                ResourceType.CPU: container.resources.limits.get("cpu")
                if container.resources and container.resources.limits
                else None,
                ResourceType.Memory: container.resources.limits.get("memory")
                if container.resources and container.resources.limits
                else None,
            },
        )
