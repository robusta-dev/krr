import abc
import asyncio
from collections import defaultdict
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable, Literal, Optional, Union

from kubernetes import client  # type: ignore
from kubernetes.client.api_client import ApiClient  # type: ignore
from kubernetes.client.models import (  # type: ignore
    V1Container,
    V1DaemonSet,
    V1Deployment,
    V1Job,
    V1Pod,
    V1PodList,
    V1StatefulSet,
)
from robusta_krr.core.models.config import settings

from robusta_krr.core.integrations.prometheus.connector import PrometheusConnector
from robusta_krr.core.integrations.prometheus.metrics.base import PrometheusMetric
from robusta_krr.core.models.allocations import RecommendationValue, ResourceAllocations, ResourceType
from robusta_krr.core.models.objects import K8sWorkload, KindLiteral, PodData

logger = logging.getLogger("krr")

AnyKubernetesAPIObject = Union[V1Deployment, V1DaemonSet, V1StatefulSet, V1Pod, V1Job]
HPAKey = tuple[str, str, str]


class BaseKindLoader(abc.ABC):
    """
    This class is used to define how to load a specific kind of Kubernetes object.
    It does not load the objects itself, but is used by the `KubeAPIWorkloadLoader` to load objects.
    """

    kinds: list[KindLiteral] = []

    def __init__(self, connector: PrometheusConnector) -> None:
        self.connector = connector
        self.cluster_selector = PrometheusMetric.get_prometheus_cluster_label()

    @property
    def kinds_to_scan(self) -> list[KindLiteral]:
        return [kind for kind in self.kinds if kind in settings.resources] if settings.resources != "*" else self.kinds

    @abc.abstractmethod
    def list_workloads(self, namespaces: Union[list[str], Literal["*"]]) -> list[K8sWorkload]:
        pass

    async def _parse_allocation(self, namespace: str, pods: list[str], container_name: str) -> ResourceAllocations:
        limits = await self.connector.loader.query(
            f"""
                avg by(resource) (
                    kube_pod_container_resource_limits{{
                        namespace="{namespace}",
                        pod=~"{'|'.join(pods)}",
                        container="{container_name}"
                        {self.cluster_selector}
                    }}
                )
            """
        )
        requests = await self.connector.loader.query(
            f"""
                avg by(resource) (
                    kube_pod_container_resource_requests{{
                        namespace="{namespace}",
                        pod=~"{'|'.join(pods)}",
                        container="{container_name}"
                        {self.cluster_selector}
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
        containers = await self.connector.loader.query(
            f"""
                count by (container) (
                    kube_pod_container_info{{
                        pod=~"{'|'.join(pods)}"
                        {self.cluster_selector}
                    }}
                )
            """
        )

        return {container["metric"]["container"] for container in containers}
