from typing import Optional

import pydantic as pd

from robusta_krr.core.models.allocations import ResourceAllocations


class PodData(pd.BaseModel):
    name: str
    deleted: bool

    def __hash__(self) -> int:
        return hash(self.name)


class K8sObjectData(pd.BaseModel):
    cluster: str
    name: str
    container: str
    pods: list[PodData]
    namespace: str
    kind: str
    allocations: ResourceAllocations

    def __str__(self) -> str:
        return f"{self.kind} {self.namespace}/{self.name}/{self.container}"

    def __hash__(self) -> int:
        return hash(str(self))

    @property
    def current_pods_count(self) -> int:
        return len([pod for pod in self.pods if not pod.deleted])

    @property
    def deleted_pods_count(self) -> int:
        return len([pod for pod in self.pods if pod.deleted])

    @property
    def pods_count(self) -> int:
        return len(self.pods)
