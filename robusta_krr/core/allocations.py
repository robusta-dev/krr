from __future__ import annotations

import enum
from typing import Self

from kubernetes.client.models import V1Container

import pydantic as pd


class ResourceType(str, enum.Enum):
    CPU = "cpu"
    Memory = "memory"


class ResourceAllocations(pd.BaseModel):
    requests: dict[ResourceType, str | None]
    limits: dict[ResourceType, str | None]

    @classmethod
    def from_container(cls, container: V1Container) -> Self:
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
