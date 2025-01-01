from __future__ import annotations

from typing import Literal, Optional

import pydantic as pd

from robusta_krr.core.models.allocations import ResourceAllocations
from robusta_krr.utils.batched import batched
from kubernetes.client.models import V1LabelSelector

KindLiteral = Literal["Deployment", "DaemonSet", "StatefulSet", "Job", "CronJob", "Rollout", "DeploymentConfig", "StrimziPodSet"]


class PodData(pd.BaseModel):
    name: str
    deleted: bool

    def __hash__(self) -> int:
        return hash(self.name)


class HPAData(pd.BaseModel):
    min_replicas: Optional[int]
    max_replicas: int
    current_replicas: Optional[int]
    desired_replicas: int
    target_cpu_utilization_percentage: Optional[float]
    target_memory_utilization_percentage: Optional[float]


PodWarning = Literal[
    "NoPrometheusPods",
    "NoPrometheusCPUMetrics",
    "NoPrometheusMemoryMetrics",
]


class K8sObjectData(pd.BaseModel):
    # NOTE: Here None means that we are running inside the cluster
    cluster: Optional[str]
    name: str
    container: str
    pods: list[PodData] = []
    hpa: Optional[HPAData]
    namespace: str
    kind: KindLiteral
    allocations: ResourceAllocations
    warnings: set[PodWarning] = set()
    labels: Optional[dict[str, str]]
    annotations: Optional[dict[str, str]]

    _api_resource = pd.PrivateAttr(None)

    def __str__(self) -> str:
        return f"{self.kind} {self.namespace}/{self.name}/{self.container}"

    def __hash__(self) -> int:
        return hash(str(self))

    def add_warning(self, warning: PodWarning) -> None:
        self.warnings.add(warning)

    @property
    def current_pods_count(self) -> int:
        return len([pod for pod in self.pods if not pod.deleted])

    @property
    def deleted_pods_count(self) -> int:
        return len([pod for pod in self.pods if pod.deleted])

    @property
    def pods_count(self) -> int:
        return len(self.pods)

    @property
    def selector(self) -> V1LabelSelector:
        if self._api_resource is None:
            raise ValueError("api_resource is not set")

        if self.kind == 'CronJob':
            return self._api_resource.spec.job_template.spec.selector
        else:
            return self._api_resource.spec.selector

    def split_into_batches(self, n: int) -> list[K8sObjectData]:
        """
        Batch this object into n objects, splitting the pods into batches of size n.
        """

        if self.pods_count <= n:
            return [self]

        return [
            K8sObjectData(
                cluster=self.cluster,
                name=self.name,
                container=self.container,
                pods=batch,
                hpa=self.hpa,
                namespace=self.namespace,
                kind=self.kind,
                allocations=self.allocations,
                labels=self.labels,
                annotations=self.annotations,
            )
            for batch in batched(self.pods, n)
        ]
