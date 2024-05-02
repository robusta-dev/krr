import abc
import logging

from typing import Literal, Union

from kubernetes.client.models import (  # type: ignore
    V1DaemonSet,
    V1Deployment,
    V1Job,
    V1Pod,
    V1StatefulSet,
)
from robusta_krr.core.models.config import settings

from robusta_krr.core.integrations.prometheus.connector import PrometheusConnector
from robusta_krr.core.models.allocations import RecommendationValue, ResourceAllocations, ResourceType
from robusta_krr.core.models.objects import K8sWorkload, KindLiteral

logger = logging.getLogger("krr")

AnyKubernetesAPIObject = Union[V1Deployment, V1DaemonSet, V1StatefulSet, V1Pod, V1Job]
HPAKey = tuple[str, str, str]


class BaseKindLoader(abc.ABC):
    """
    This class is used to define how to load a specific kind of Kubernetes object.
    It does not load the objects itself, but is used by the `KubeAPIWorkloadLoader` to load objects.
    """

    kinds: list[KindLiteral] = []

    def __init__(self, cluster: str, prometheus: PrometheusConnector) -> None:
        self.cluster = cluster
        self.prometheus = prometheus

    @property
    def kinds_to_scan(self) -> list[KindLiteral]:
        return [kind for kind in self.kinds if kind in settings.resources] if settings.resources != "*" else self.kinds

    @property
    def cluster_selector(self) -> str:
        if settings.prometheus_label is not None:
            return f'{settings.prometheus_cluster_label}="{settings.prometheus_label}",'

        if settings.prometheus_cluster_label is None:
            return ""

        return f'{settings.prometheus_cluster_label}="{self.cluster}",' if self.cluster else ""

    @abc.abstractmethod
    def list_workloads(self, namespaces: Union[list[str], Literal["*"]]) -> list[K8sWorkload]:
        pass

    async def _parse_allocation(self, namespace: str, pods: list[str], container_name: str) -> ResourceAllocations:
        limits = await self.prometheus.loader.query(
            f"""
                avg by(resource) (
                    kube_pod_container_resource_limits{{
                        {self.cluster_selector}
                        namespace="{namespace}",
                        pod=~"{'|'.join(pods)}",
                        container="{container_name}"
                    }}
                )
            """
        )
        requests = await self.prometheus.loader.query(
            f"""
                avg by(resource) (
                    kube_pod_container_resource_requests{{
                        {self.cluster_selector}
                        namespace="{namespace}",
                        pod=~"{'|'.join(pods)}",
                        container="{container_name}"
                    }}
                )
            """
        )
        requests_values: dict[ResourceType, RecommendationValue] = {ResourceType.CPU: None, ResourceType.Memory: None}
        limits_values: dict[ResourceType, RecommendationValue] = {ResourceType.CPU: None, ResourceType.Memory: None}
        for limit in limits:
            if limit["metric"]["resource"] == ResourceType.CPU:
                limits_values[ResourceType.CPU] = float(limit["value"][1])
            elif limit["metric"]["resource"] == ResourceType.Memory:
                limits_values[ResourceType.Memory] = float(limit["value"][1])

        for request in requests:
            if request["metric"]["resource"] == ResourceType.CPU:
                requests_values[ResourceType.CPU] = float(request["value"][1])
            elif request["metric"]["resource"] == ResourceType.Memory:
                requests_values[ResourceType.Memory] = float(request["value"][1])
        return ResourceAllocations(requests=requests_values, limits=limits_values)

    async def _list_containers_in_pods(self, pods: list[str]) -> set[str]:
        containers = await self.prometheus.loader.query(
            f"""
                count by (container) (
                    kube_pod_container_info{{
                        {self.cluster_selector}
                        pod=~"{'|'.join(pods)}"
                    }}
                )
            """
        )

        return {container["metric"]["container"] for container in containers}
