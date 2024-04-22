import abc
import asyncio
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

from robusta_krr.core.integrations.prometheus.loader import PrometheusMetricsLoader
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

    kind: KindLiteral

    def __init__(self, metrics_loader: PrometheusMetricsLoader) -> None:
        self.metrics_loader = metrics_loader

    @abc.abstractmethod
    def list_workloads(self, namespaces: Union[list[str], Literal["*"]], label_selector: str) -> list[K8sWorkload]:
        pass

    async def __parse_allocation(self, namespace: str, pod_selector: str, container_name: str) -> ResourceAllocations:
        limits = await self.metrics_loader.loader.query(
            "avg by(resource) (kube_pod_container_resource_limits{"
            f'namespace="{namespace}", '
            f'pod=~"{pod_selector}", '
            f'container="{container_name}"'
            "})"
        )
        requests = await self.metrics_loader.loader.query(
            "avg by(resource) (kube_pod_container_resource_requests{"
            f'namespace="{namespace}", '
            f'pod=~"{pod_selector}", '
            f'container="{container_name}"'
            "})"
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

    async def __build_from_owner(
        self, namespace: str, app_name: str, containers: list[str], pod_names: list[str]
    ) -> list[K8sWorkload]:
        return [
            K8sWorkload(
                cluster=None,
                namespace=namespace,
                name=app_name,
                kind="Deployment",
                container=container_name,
                allocations=await self.__parse_allocation(namespace, "|".join(pod_names), container_name),  # find
                pods=[PodData(name=pod_name, deleted=False) for pod_name in pod_names],  # list pods
            )
            for container_name in containers
        ]

    async def _list_containers(self, namespace: str, pod_selector: str) -> list[str]:
        containers = await self.metrics_loader.loader.query(
            f"""
                count by (container) (
                    kube_pod_container_info{{
                        namespace="{namespace}",
                        pod=~"{pod_selector}"
                    }}
                )
            """
        )
        return [container["metric"]["container"] for container in containers]

    async def _list_containers_in_pods(
        self, app_name: str, pod_owner_kind: str, namespace: str, owner_name: str
    ) -> list[K8sWorkload]:
        if pod_owner_kind == "ReplicaSet":
            # owner_name is ReplicaSet names
            pods = await self.metrics_loader.loader.query(
                f"""
                    count by (owner_name, replicaset, pod) (
                        kube_pod_owner{{
                            namespace="{namespace}",
                            owner_name=~"{owner_name}", '
                            owner_kind="ReplicaSet"
                        }}
                    )
                """
            )
            if pods is None or len(pods) == 0:
                return []  # no container
            # [{'metric': {'owner_name': 'wbjs-algorithm-base-565b645489', 'pod': 'wbjs-algorithm-base-565b645489-jqt4x'}, 'value': [1685529217, '1']},
            #  {'metric': {'owner_name': 'wbjs-algorithm-base-565b645489', 'pod': 'wbjs-algorithm-base-565b645489-lj9qg'}, 'value': [1685529217, '1']}]
            pod_names = [pod["metric"]["pod"] for pod in pods]
            container_names = await self._list_containers(namespace, "|".join(pod_names))
            return await self.__build_from_owner(namespace, app_name, container_names, pod_names)
        return []
